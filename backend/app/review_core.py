from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .config import CORE_DIR, settings
from .contracts import (
    ContractError,
    normalize_feedback,
    normalize_router,
    normalize_rule_evaluation,
)
from .llm import LLMError, get_provider
from .verification import FACT_SENSITIVE_RULE_IDS, make_verification_context, verification_guard_text
from .fact_search import verify_article_facts
from .feedback_clustering import cluster_failed_rules

logger = logging.getLogger("mall_content_os.review")

REGISTRY = CORE_DIR / "registry" / "compiled_rule_registry.json"
GATES = CORE_DIR / "portable" / "runtime" / "gate_registry.json"
PROMPTS = CORE_DIR / "portable" / "prompts"


# Rules whose PASS state can support useful author-facing positive feedback.
# Excluded: verification/global guardrails, conditional反证 rules, final/gate rules,
# and rules where PASS mostly means "no problem detected" rather than a positive asset.
STRENGTH_ELIGIBLE_RULE_IDS = {
    # Strong content-value signals. PASS is necessary but still not sufficient.
    "T001", "T002", "T003", "T004",
    "T101", "T102", "T103",
    "E001", "E101", "E201", "E301", "E401",
    "I001", "I002", "I004", "I101", "I201",
    "S001", "S002", "S003", "S005", "S006",
    "S101", "S201", "S301",
}

# Every published strength must include at least one anchor Rule whose PASS can represent
# a distinctive content asset, rather than merely adequate evidence or absence of error.
# Evidence Rules may support a strength, but cannot create one by themselves.
STRENGTH_ANCHOR_RULE_IDS = {
    "T001", "T002", "T003", "T004",
    "T101", "T102", "T103",
    "I001", "I002", "I004", "I101", "I201",
    "S001", "S002", "S005", "S101", "S201", "S301",
}

# Fixed primary-dimension ownership by Rule stage. Dimension ownership is structural,
# not inferred by the model at runtime. FINAL meta rules F001/F002 are excluded; F003
# is a judgement-quality rule and therefore belongs to 观点质量.
DIM_MAP = {
    "TOPIC": "选题价值",
    "EVIDENCE": "证据支撑",
    "GLOBAL": "证据支撑",
    "INSIGHT": "观点质量",
    "STRUCTURE": "结构逻辑",
    "EXPRESSION": "表达质量",
    "FINAL": "观点质量",
}

# FINAL meta rules are deterministic summaries of upstream execution state, not fresh
# article judgements. They are derived after model evaluation and never shown as
# standalone author-facing problems or dimension evidence.
DERIVED_META_RULE_IDS = {"F001", "F002"}
FIXED_DIMENSIONS = ["选题价值", "证据支撑", "观点质量", "结构逻辑", "表达质量"]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rules_by_id():
    return {r["rule_id"]: r for r in load_json(REGISTRY)["rules"]}


def applicable_rule_ids(content_type: str):
    gates = load_json(GATES)["gates"]
    out = []
    for gate_name in ["TOPIC", "EVIDENCE", "INSIGHT", "STRUCTURE", "FINAL"]:
        g = gates[gate_name]
        out += g.get("always", [])
        out += g.get("by_type", {}).get(content_type, [])
        out += g.get("all_expression", [])
    reg = rules_by_id()
    seen = set()
    final = []
    for rid in out:
        if rid in seen or rid not in reg:
            continue
        r = reg[rid]
        if content_type in r.get("applies_to", []) or "ALL" in r.get("applies_to", []):
            seen.add(rid)
            final.append(rid)
    return final


def model_rule_ids(content_type: str):
    return [rid for rid in applicable_rule_ids(content_type) if rid not in DERIVED_META_RULE_IDS]


def compact_rules(content_type: str):
    reg = rules_by_id()
    keys = [
        "rule_id",
        "name",
        "stage",
        "severity",
        "evaluation_question",
        "pass_condition",
        "fail_condition",
        "exceptions",
    ]
    return [{k: reg[rid].get(k) for k in keys} for rid in model_rule_ids(content_type)]


def validate_eval(result: dict[str, Any], content_type: str, *, allow_derived_missing: bool = False):
    supplied = set(model_rule_ids(content_type) if allow_derived_missing else applicable_rule_ids(content_type))
    buckets = []
    buckets += result.get("passed_rule_ids", [])
    buckets += result.get("na_rule_ids", [])
    buckets += [x["rule_id"] for x in result.get("failed_rules", [])]
    buckets += [x["rule_id"] for x in result.get("unresolved_rules", [])]
    unknown = set(buckets) - supplied
    if unknown:
        raise ValueError(f"Model returned unsupplied Rule IDs: {sorted(unknown)}")
    if len(buckets) != len(set(buckets)):
        raise ValueError("A Rule appears in multiple status buckets.")
    missing = supplied - set(buckets)
    if missing:
        raise ValueError(f"Model omitted Rule IDs: {sorted(missing)}")


def _render(template: str, values: dict[str, Any]):
    for k, v in values.items():
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False, indent=2)
        template = template.replace("{{" + k + "}}", v)
    return template


async def _schema_repair(
    *,
    provider,
    contract_name: str,
    raw_data: dict[str, Any],
    exact_schema_text: str,
    invariants: str,
) -> dict[str, Any]:
    """One bounded semantic-shape repair.

    It may only remap/complete output structure using already present judgements.
    It may not perform a fresh article review.
    """
    system = (
        f"你是 {contract_name}_CONTRACT_REPAIR。"
        "你只能整理上一轮模型输出的字段、枚举值和 JSON 结构，使其满足给定契约。"
        "不得重新阅读文章、不得产生新判断、不得改变 PASS/FAIL/NA/UNRESOLVED 的实质结论。"
        "若原始输出无法支持某必填字段，必须使用最保守的 UNRESOLVED/空值方式，而不是猜测。"
        "只输出一个 JSON 对象。"
    )
    user = (
        "CONTRACT:\n" + exact_schema_text
        + "\n\nINVARIANTS:\n" + invariants
        + "\n\nPREVIOUS_OUTPUT:\n"
        + json.dumps(raw_data, ensure_ascii=False, indent=2)
    )
    return await provider.generate_json(system, user)


async def route_content_type(article: str) -> str:
    # Routing is a bounded classification task; use the secondary/Flash model.
    provider = get_provider(secondary=True)
    prompt = (PROMPTS / "04_router.md").read_text(encoding="utf-8")

    # First attempt.
    raw = await provider.generate_json(
        "你是 CONTENT_TYPE_ROUTER。只分类，不评价质量。必须严格按用户消息中的 JSON 契约输出。",
        prompt + "\n\nARTICLE:\n" + article,
    )
    try:
        return normalize_router(raw)["content_type"]
    except ContractError:
        # One targeted classification retry is allowed: Router itself is only a classifier.
        retry_system = (
            "你是 CONTENT_TYPE_ROUTER_RETRY。只做 A/B/C/D/E 分类，不评价质量。"
            "必须只输出 JSON："
            '{"content_type":"A|B|C|D|E","confidence":0.0,"primary_value":"一句话"}。'
            "content_type 必须是单个大写字母 A/B/C/D/E，不能输出 D类、类型D、type 等其他字段名。"
        )
        retry_user = prompt + "\n\nARTICLE:\n" + article
        raw2 = await provider.generate_json(retry_system, retry_user)
        try:
            return normalize_router(raw2)["content_type"]
        except ContractError as exc:
            keys = sorted(raw2.keys()) if isinstance(raw2, dict) else []
            raise LLMError(
                "自动判断文章类型失败。请在网页“文章类型”中手动选择 A/B/C/D/E 后重试。"
                f" Router returned keys={keys}"
            ) from exc


async def evaluate_rules(article: str, content_type: str, verification_context):
    provider = get_provider()
    rules = compact_rules(content_type)
    supplied_ids = [r["rule_id"] for r in rules]
    evaluator = (PROMPTS / "01_rule_batch_evaluator.md").read_text(encoding="utf-8")
    user = _render(
        evaluator,
        {
            "CONTENT_TYPE": content_type,
            "APPLICABLE_RULES_COMPACT": rules,
            "VERIFICATION_RESULTS": verification_context.results,
            "VERIFICATION_GUARD": verification_guard_text(verification_context),
            "ARTICLE": article,
        },
    )

    raw = await provider.generate_json(
        "你是严格的 RULE_BATCH_EVALUATOR。只能执行输入 Rules。必须逐条遵守提示中的 FAIL-FIRST 决策树：先查 fail_condition，再查 pass_condition，并按冲突裁决原则决定 PASS/FAIL/NA/UNRESOLVED。不得用局部 PASS 理由覆盖已经成立的 FAIL。必须严格按指定 JSON 契约输出。",
        user,
    )
    try:
        return normalize_rule_evaluation(
            raw, content_type=content_type, supplied_rule_ids=supplied_ids, verification_context=verification_context
        )
    except ContractError as first_exc:
        schema = (CORE_DIR / "portable" / "schemas" / "rule_evaluation_schema.json").read_text(
            encoding="utf-8"
        )
        repaired = await _schema_repair(
            provider=provider,
            contract_name="RULE_EVALUATION",
            raw_data=raw,
            exact_schema_text=schema,
            invariants=(
                f"CONTENT_TYPE 必须是 {content_type}。\n"
                f"SUPPLIED_RULE_IDS={json.dumps(supplied_ids, ensure_ascii=False)}。\n"
                "每个 supplied Rule 必须且只能出现在 PASS/FAIL/NA/UNRESOLVED 一个桶中。"
                "不得新增 Rule ID。FAIL 必须同时保留原输出中已有的 article_evidence 与 match_explanation；任一缺失都必须转为 UNRESOLVED，不得猜测补全。"
            ),
        )
        try:
            return normalize_rule_evaluation(
                repaired, content_type=content_type, supplied_rule_ids=supplied_ids, verification_context=verification_context
            )
        except ContractError as exc:
            raise LLMError(
                f"Rule Evaluator 输出未通过契约校验：{exc}. "
                "为防止错误审稿，本次结果已中止。"
            ) from first_exc


async def evaluate_rule_subset(article: str, content_type: str, verification_context, rule_ids: list[str]):
    """Evaluate only an explicit subset of already-applicable Rules.

    Used by the fact-check performance path after the main evaluator has run in
    parallel with web search. It cannot introduce new Rules.
    """
    applicable = set(applicable_rule_ids(content_type))
    supplied_ids = [rid for rid in rule_ids if rid in applicable]
    if not supplied_ids:
        return None
    reg = rules_by_id()
    keys = [
        "rule_id", "name", "stage", "severity", "evaluation_question",
        "pass_condition", "fail_condition", "exceptions",
    ]
    rules = [{k: reg[rid].get(k) for k in keys} for rid in supplied_ids]
    evaluator = (PROMPTS / "01_rule_batch_evaluator.md").read_text(encoding="utf-8")
    user = _render(
        evaluator,
        {
            "CONTENT_TYPE": content_type,
            "APPLICABLE_RULES_COMPACT": rules,
            "VERIFICATION_RESULTS": verification_context.results,
            "VERIFICATION_GUARD": verification_guard_text(verification_context),
            "ARTICLE": article,
        },
    )
    # Fact-sensitive recheck is a bounded subset judgement; use Flash.
    provider = get_provider(secondary=True)
    raw = await provider.generate_json(
        "你是 FACT_SENSITIVE_RULE_ADJUDICATOR。只执行输入的事实敏感 Rules，不得重审其他规则。",
        user,
    )
    return normalize_rule_evaluation(
        raw,
        content_type=content_type,
        supplied_rule_ids=supplied_ids,
        verification_context=verification_context,
    )


def merge_rule_subset(eval_result: dict[str, Any], subset_result: dict[str, Any] | None, rule_ids: list[str]):
    """Replace statuses for the selected Rule IDs while preserving all others."""
    if not subset_result:
        return eval_result
    targets = set(rule_ids)
    eval_result["passed_rule_ids"] = [x for x in eval_result.get("passed_rule_ids", []) if x not in targets]
    eval_result["na_rule_ids"] = [x for x in eval_result.get("na_rule_ids", []) if x not in targets]
    eval_result["failed_rules"] = [x for x in eval_result.get("failed_rules", []) if x.get("rule_id") not in targets]
    eval_result["unresolved_rules"] = [x for x in eval_result.get("unresolved_rules", []) if x.get("rule_id") not in targets]
    eval_result["passed_rule_ids"] += subset_result.get("passed_rule_ids", [])
    eval_result["na_rule_ids"] += subset_result.get("na_rule_ids", [])
    eval_result["failed_rules"] += subset_result.get("failed_rules", [])
    eval_result["unresolved_rules"] += subset_result.get("unresolved_rules", [])
    eval_result["evaluated_rule_ids"] = list(applicable_rule_ids(eval_result["content_type"]))
    return eval_result


def verification_requires_rule_recheck(results: list[dict[str, Any]]) -> bool:
    """Only material adverse search findings justify an extra evaluator call.

    Confirmed/basic/no-source findings do not need to delay the review. A high-
    importance questionable claim or any contradiction can materially affect G001/G002.
    """
    for item in results:
        status = str(item.get("status", "")).lower()
        importance = str(item.get("importance", "medium")).lower()
        if status == "contradicted":
            return True
        if status == "questionable" and importance == "high":
            return True
    return False


async def adjudicate_unresolved(
    article: str, content_type: str, eval_result: dict[str, Any], verification_context
):
    unresolved = eval_result.get("unresolved_rules", [])
    if not unresolved:
        return eval_result

    unresolved_ids = [x["rule_id"] for x in unresolved]
    reg = rules_by_id()
    keys = [
        "rule_id",
        "name",
        "stage",
        "severity",
        "evaluation_question",
        "pass_condition",
        "fail_condition",
        "exceptions",
    ]
    target_rules = [{k: reg[rid].get(k) for k in keys} for rid in unresolved_ids]
    evaluator = (PROMPTS / "01_rule_batch_evaluator.md").read_text(encoding="utf-8")
    user = _render(
        evaluator,
        {
            "CONTENT_TYPE": content_type,
            "APPLICABLE_RULES_COMPACT": target_rules,
            "VERIFICATION_RESULTS": verification_context.results,
            "VERIFICATION_GUARD": verification_guard_text(verification_context),
            "ARTICLE": article,
        },
    )

    # UNRESOLVED adjudication is narrow and fail-safe; use Flash.
    provider = get_provider(secondary=True)
    raw = await provider.generate_json(
        "你是 TARGETED_ADJUDICATOR。只复核输入的 UNRESOLVED Rules，不得重审其他规则。",
        user,
    )
    try:
        result = normalize_rule_evaluation(
            raw, content_type=content_type, supplied_rule_ids=unresolved_ids, verification_context=verification_context
        )
    except ContractError:
        # Adjudication is optional. Fail-safe means preserve unresolved, not fail the review.
        return eval_result

    eval_result["passed_rule_ids"] += result.get("passed_rule_ids", [])
    eval_result["na_rule_ids"] += result.get("na_rule_ids", [])
    eval_result["failed_rules"] += result.get("failed_rules", [])
    eval_result["unresolved_rules"] = result.get("unresolved_rules", [])
    eval_result["evaluated_rule_ids"] = list(applicable_rule_ids(content_type))
    return eval_result


def _remove_rule_from_buckets(eval_result: dict[str, Any], rule_id: str) -> None:
    eval_result["passed_rule_ids"] = [x for x in eval_result.get("passed_rule_ids", []) if x != rule_id]
    eval_result["na_rule_ids"] = [x for x in eval_result.get("na_rule_ids", []) if x != rule_id]
    eval_result["failed_rules"] = [x for x in eval_result.get("failed_rules", []) if x.get("rule_id") != rule_id]
    eval_result["unresolved_rules"] = [x for x in eval_result.get("unresolved_rules", []) if x.get("rule_id") != rule_id]


def derive_meta_rules(eval_result: dict[str, Any], content_type: str) -> dict[str, Any]:
    """Derive FINAL meta rules without asking the model to re-judge the article.

    F001 means "an upstream BLOCKER remains" and therefore mirrors already-confirmed
    upstream BLOCKER FAILs. F002 verifies severity execution; runtime severity is read
    directly from the registry, so a successfully normalized evaluation passes F002.
    """
    applicable = set(applicable_rule_ids(content_type))
    reg = rules_by_id()
    for rid in DERIVED_META_RULE_IDS:
        _remove_rule_from_buckets(eval_result, rid)

    upstream_blockers = []
    for item in eval_result.get("failed_rules", []):
        rid = item.get("rule_id")
        rule = reg.get(rid, {})
        if rid not in DERIVED_META_RULE_IDS and rule.get("severity") == "BLOCKER" and rule.get("stage") != "FINAL":
            upstream_blockers.append(item)

    if "F001" in applicable:
        if upstream_blockers:
            evidence = []
            for item in upstream_blockers:
                for ev in item.get("article_evidence", []):
                    if ev and ev not in evidence:
                        evidence.append(ev)
            eval_result.setdefault("failed_rules", []).append({
                "rule_id": "F001",
                "article_evidence": evidence[:6] or ["上游 BLOCKER 已由现有 Rule 结果确认。"],
                "match_explanation": "存在未解决的上游 BLOCKER：" + ", ".join(x.get("rule_id", "") for x in upstream_blockers),
            })
        else:
            eval_result.setdefault("passed_rule_ids", []).append("F001")

    if "F002" in applicable:
        eval_result.setdefault("passed_rule_ids", []).append("F002")

    eval_result["evaluated_rule_ids"] = list(applicable_rule_ids(content_type))
    return eval_result


def user_facing_failed_rules(eval_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in eval_result.get("failed_rules", []) if x.get("rule_id") not in DERIVED_META_RULE_IDS]


def dimension_fail_context(eval_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Build dimension provenance from confirmed non-meta FAIL Rules only."""
    reg = rules_by_id()
    out: list[dict[str, Any]] = []
    for item in user_facing_failed_rules(eval_result):
        rid = item.get("rule_id")
        rule = reg.get(rid, {})
        dim = DIM_MAP.get(rule.get("stage"))
        if not dim:
            continue
        out.append({
            "rule_id": rid,
            "name": rule.get("name"),
            "stage": rule.get("stage"),
            "dimension": dim,
            "severity": rule.get("severity"),
            "fail_condition": rule.get("fail_condition"),
            "article_evidence": item.get("article_evidence", []),
            "match_explanation": item.get("match_explanation", ""),
        })
    return out


def dimension_fail_groups(eval_result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group confirmed FAILs by their fixed primary Dimension ownership."""
    groups = {dim: [] for dim in FIXED_DIMENSIONS}
    for item in dimension_fail_context(eval_result):
        groups[item["dimension"]].append(item)
    return groups


def deterministic_dimension_fallback(eval_result: dict[str, Any]) -> dict[str, Any]:
    """Conservative fail-safe when the secondary Dimension Evaluator is unavailable."""
    dims = {k: "达标" for k in FIXED_DIMENSIONS}
    ctx = dimension_fail_context(eval_result)
    by_dim: dict[str, list[dict[str, Any]]] = {}
    for item in ctx:
        by_dim.setdefault(item["dimension"], []).append(item)
    for dim, items in by_dim.items():
        if any(x.get("severity") == "BLOCKER" for x in items):
            dims[dim] = "有明显问题"
        elif sum(1 for x in items if x.get("severity") == "MAJOR") >= 2:
            dims[dim] = "有明显问题"
    return {
        "dimension_states": dims,
        "final_judgement": "需要修改" if "有明显问题" in dims.values() else "可以继续",
        "dimension_reasons": {},
    }


def validate_dimension_result(raw: dict[str, Any], eval_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Dimension Evaluator output must be an object")
    dims = raw.get("dimension_states")
    if not isinstance(dims, dict) or set(dims.keys()) != set(FIXED_DIMENSIONS):
        raise ValueError("dimension_states must contain exactly the five fixed dimensions")
    if any(v not in {"达标", "有明显问题"} for v in dims.values()):
        raise ValueError("dimension_states contains unsupported state")

    ctx = dimension_fail_context(eval_result)
    mapped_dims = {x["dimension"] for x in ctx}
    blocker_dims = {x["dimension"] for x in ctx if x.get("severity") == "BLOCKER"}
    for dim in FIXED_DIMENSIONS:
        if dim not in mapped_dims and dims[dim] != "达标":
            raise ValueError(f"Dimension provenance violation: {dim} has no mapped FAIL Rule")
        if dim in blocker_dims:
            # BLOCKER is no longer a direct Gate trigger. It is a mandatory dimension
            # failure signal, which then deterministically produces the release state.
            dims[dim] = "有明显问题"

    final = "需要修改" if "有明显问题" in dims.values() else "可以继续"
    reasons = raw.get("dimension_reasons", {})
    if not isinstance(reasons, dict):
        reasons = {}
    return {"dimension_states": dims, "final_judgement": final, "dimension_reasons": reasons}


async def evaluate_dimensions_and_gate(article: str, content_type: str, eval_result: dict[str, Any]) -> dict[str, Any]:
    """Dimension is the quality judge; Gate is only the deterministic release switch."""
    ctx = dimension_fail_context(eval_result)
    if not ctx:
        dims = {k: "达标" for k in FIXED_DIMENSIONS}
        return {"dimension_states": dims, "final_judgement": "可以继续", "dimension_reasons": {}}

    prompt_path = PROMPTS / "06_dimension_gate_evaluator.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    user = _render(prompt, {
        "CONTENT_TYPE": content_type,
        "DIMENSION_FAIL_GROUPS": dimension_fail_groups(eval_result),
    })
    provider = get_provider(secondary=True)
    raw = await provider.generate_json(
        "你是 DIMENSION_EVALUATOR。Rule 所属维度已由系统固定分类。你只能在每条 Rule 已分配的唯一维度内判断影响程度，不得跨维度扩散，不得重新判 Rule，不得新增问题。BLOCKER 必须使其所属维度为有明显问题。只输出指定 JSON。",
        user,
    )
    return validate_dimension_result(raw, eval_result)


def _valid_negative_item(item: Any, failed_ids: set[str], article: str) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    text = str(item.get("text", "")).strip()
    support = [str(x).strip() for x in item.get("supporting_rule_ids", []) if str(x).strip()]
    evidence = [str(x).strip() for x in item.get("article_evidence", []) if str(x).strip()]
    if not text or not support or not evidence:
        return None
    if not set(support).issubset(failed_ids):
        return None
    if any(ev not in article for ev in evidence):
        return None
    return {"text": text, "supporting_rule_ids": list(dict.fromkeys(support)), "article_evidence": evidence}

def deterministic_feedback_fallback(eval_result: dict[str, Any]) -> dict[str, Any]:
    """Clustered fail-safe using only confirmed FAIL provenance."""
    failed = user_facing_failed_rules(eval_result)
    if not failed:
        return {"core_diagnosis": None, "issue_candidates": []}

    reg = rules_by_id()
    clusters = cluster_failed_rules(failed, reg)
    issues: list[dict[str, Any]] = []
    for c in clusters:
        ids = [rid for rid in c.get("supporting_rule_ids", []) if rid not in DERIVED_META_RULE_IDS]
        if not ids:
            continue
        ev = [x for x in c.get("article_evidence", []) if x]
        if len(ids) == 1:
            rid = ids[0]
            f = next((x for x in failed if x.get("rule_id") == rid), None)
            if not f:
                continue
            text = f"{reg[rid]['name']}：{f.get('match_explanation', '')}"
            ev = f.get("article_evidence", []) or ev
        else:
            text = f"{c.get('cluster_hint', '同源问题')}：多个已 FAIL Rules 指向同一上游问题。"
        if ev:
            issues.append({"text": text, "supporting_rule_ids": ids, "article_evidence": ev})

    if not issues:
        # Last-resort deterministic rendering. This is only used when clustering itself
        # returns unusable data; it never invents a new editorial criterion.
        for f in failed:
            rid = f.get("rule_id")
            ev = f.get("article_evidence", [])
            if rid and ev:
                issues.append({
                    "text": f"{reg[rid]['name']}：{f.get('match_explanation', '')}",
                    "supporting_rule_ids": [rid],
                    "article_evidence": ev,
                })

    return {"core_diagnosis": issues[0] if issues else None, "issue_candidates": issues}


async def extract_strengths(
    article: str,
    content_type: str,
    eval_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract positive author feedback from selected PASS Rules only."""
    passed = [
        rid for rid in eval_result.get("passed_rule_ids", [])
        if rid in STRENGTH_ELIGIBLE_RULE_IDS
    ]
    if not passed:
        return []

    reg = rules_by_id()
    keys = [
        "rule_id", "name", "stage", "evaluation_question",
        "pass_condition", "exceptions",
    ]
    strength_rules = [{k: reg[rid].get(k) for k in keys} for rid in passed]
    prompt = (PROMPTS / "05_strength_extractor.md").read_text(encoding="utf-8")
    user = _render(
        prompt,
        {
            "CONTENT_TYPE": content_type,
            "PASSED_STRENGTH_RULES": strength_rules,
            "ARTICLE": article,
        },
    )

    provider = get_provider(secondary=True)
    try:
        raw = await provider.generate_json(
            "你是 STRENGTH_EXTRACTOR。只能从已 PASS 的指定 Rules 提取值得保留内容；No PASS Rule, No Strength。只输出 JSON。",
            user,
        )
        strengths_raw = raw.get("strengths", []) if isinstance(raw, dict) else []
        if not isinstance(strengths_raw, list):
            return []

        out: list[dict[str, Any]] = []
        passed_set = set(passed)
        for item in strengths_raw[:4]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            support = [str(x).strip() for x in item.get("supporting_rule_ids", []) if str(x).strip()]
            evidence = [str(x).strip() for x in item.get("article_evidence", []) if str(x).strip()]
            significant = item.get("significant_asset") is True
            deletion_harm = str(item.get("deletion_harm", "")).strip()
            if not text or not support or not evidence or not significant or not deletion_harm:
                continue
            if not set(support).issubset(passed_set):
                continue
            if not (set(support) & STRENGTH_ANCHOR_RULE_IDS):
                continue
            if any(ev not in article for ev in evidence):
                continue
            out.append({
                "text": text,
                "supporting_rule_ids": list(dict.fromkeys(support)),
                "article_evidence": evidence,
            })
        return out
    except Exception as exc:
        logger.warning("Strength Extractor failed; returning no strengths: %s", exc)
        return []


async def compose_feedback(article: str, eval_result: dict[str, Any], verification_results: list[dict[str, Any]]):
    """Problem clusterer only. It cannot judge dimensions or release state."""
    failed = user_facing_failed_rules(eval_result)
    if not failed:
        return {"core_diagnosis": None, "issue_candidates": []}

    reg = rules_by_id()
    clusters = cluster_failed_rules(failed, reg)
    if not clusters:
        return deterministic_feedback_fallback(eval_result)

    provider = get_provider(secondary=True)
    prompt = (PROMPTS / "02_feedback_composer.md").read_text(encoding="utf-8")
    user = _render(prompt, {
        "FAILED_RULES_ONLY": failed,
        "FAILED_RULE_CLUSTERS": clusters,
        "VERIFICATION_RESULTS": verification_results,
        "ARTICLE": article,
    })
    try:
        raw = await provider.generate_json(
            "你是 PROBLEM_CLUSTERER。只能把已 FAIL Rules 聚合成同源作者问题。不得判断五维、不得判断是否发布、不得新增审稿标准。只输出指定 JSON。",
            user,
        )
        failed_ids = {x.get("rule_id") for x in failed if x.get("rule_id")}
        raw_issues = raw.get("issue_candidates", []) if isinstance(raw, dict) else []
        issues: list[dict[str, Any]] = []
        if isinstance(raw_issues, list):
            for item in raw_issues:
                valid = _valid_negative_item(item, failed_ids, article)
                if valid:
                    issues.append(valid)

        core = _valid_negative_item(raw.get("core_diagnosis"), failed_ids, article) if isinstance(raw, dict) else None
        if core is None and issues:
            core = issues[0]

        # Item-level tolerance: malformed items are discarded, not a reason to reject
        # the entire response. If nothing valid remains, use deterministic clustering.
        if not issues:
            return deterministic_feedback_fallback(eval_result)
        return {"core_diagnosis": core, "issue_candidates": issues}
    except Exception as exc:
        logger.warning("Problem Clusterer failed; clustered fallback: %s", exc)
        return deterministic_feedback_fallback(eval_result)

def registry_hash():
    return load_json(REGISTRY).get("registry_semantic_hash", "unknown")


def _emit_progress(progress_callback: Callable[[str, str], None] | None, stage: str, message: str) -> None:
    if progress_callback:
        try:
            progress_callback(stage, message)
        except Exception:
            logger.debug("progress callback failed", exc_info=True)


async def review_article(
    article: str, content_type: str, verify_facts: bool = False,
    progress_callback: Callable[[str, str], None] | None = None,
):
    review_started = time.perf_counter()
    requested_type = content_type
    logger.info(
        "[review] start content_type=%s article_chars=%d verify_facts=%s",
        requested_type,
        len(article),
        verify_facts,
    )

    _emit_progress(progress_callback, "STARTING", "正在准备审核")

    if content_type == "AUTO":
        _emit_progress(progress_callback, "ROUTING", "正在判断文章类型")
        t0 = time.perf_counter()
        logger.info("[review] route_content_type start")
        try:
            content_type = await asyncio.wait_for(
                route_content_type(article),
                timeout=settings.llm_router_stage_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise LLMError("自动判断文章类型超时。请手动选择 A/B/C/D/E 后重试。") from exc
        logger.info(
            "[review] route_content_type done elapsed=%.2fs resolved_type=%s",
            time.perf_counter() - t0,
            content_type,
        )

    verification_results: list[dict[str, Any]] = []
    verification_state = "NOT_RUN"
    verification_note = "外部事实核验未执行；系统不得仅以‘无法核实/缺少来源’为理由触发事实类 FAIL。"

    # Performance path: fact search and the main Rule Evaluator run concurrently.
    # The main evaluator uses NOT_RUN verification, so it cannot punish unknown facts.
    # After search finishes, only the existing fact-sensitive Rules (G001/G002) are
    # selectively rechecked when search finds a material adverse signal.
    preliminary_verification_context = make_verification_context(False, [], state="NOT_RUN")

    _emit_progress(
        progress_callback,
        "FACT_CHECKING" if verify_facts else "EVALUATING",
        "正在并行执行规则审核与事实核验" if verify_facts else "正在执行规则审核",
    )
    parallel_started = time.perf_counter()
    logger.info("[review] parallel_core start verify_facts=%s content_type=%s", verify_facts, content_type)

    async def _main_evaluator_task():
        t = time.perf_counter()
        logger.info("[review] evaluate_rules start content_type=%s verification=NOT_RUN", content_type)
        try:
            value = await asyncio.wait_for(
                evaluate_rules(article, content_type, preliminary_verification_context),
                timeout=settings.llm_evaluator_stage_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise LLMError(
                f"Rule Evaluator 超过 {settings.llm_evaluator_stage_timeout_seconds:.0f} 秒仍未完成，本次审核安全中止。"
            ) from exc
        logger.info(
            "[review] evaluate_rules done elapsed=%.2fs failed=%d unresolved=%d failed_ids=%s unresolved_ids=%s",
            time.perf_counter() - t,
            len(value.get("failed_rules", [])),
            len(value.get("unresolved_rules", [])),
            [x.get("rule_id") for x in value.get("failed_rules", [])],
            [x.get("rule_id") for x in value.get("unresolved_rules", [])],
        )
        return value

    async def _fact_search_task():
        if not verify_facts:
            return None
        t = time.perf_counter()
        logger.info("[review] fact_search start")
        try:
            value = await verify_article_facts(article, content_type)
            logger.info(
                "[review] fact_search done elapsed=%.2fs state=%s results=%d",
                time.perf_counter() - t,
                value.state,
                len(value.results),
            )
            return value
        except Exception as exc:
            logger.warning("[review] fact_search degraded elapsed=%.2fs error=%s", time.perf_counter() - t, exc)
            return None

    eval_result, fact_outcome = await asyncio.gather(_main_evaluator_task(), _fact_search_task())
    logger.info("[review] parallel_core done elapsed=%.2fs", time.perf_counter() - parallel_started)

    if verify_facts:
        if fact_outcome is not None:
            verification_results = fact_outcome.results
            verification_state = fact_outcome.state
            verification_note = fact_outcome.note
        else:
            verification_state = "NOT_RUN"
            verification_results = []
            verification_note = "事实搜索发生异常，本次审核已自动降级为未联网核验；不会因为搜索失败判文章事实错误。"

    verification_context = make_verification_context(verify_facts, verification_results, state=verification_state)
    validate_eval(eval_result, content_type, allow_derived_missing=True)

    # Only adverse, high-impact search findings trigger a small targeted recheck.
    fact_rule_ids = [rid for rid in FACT_SENSITIVE_RULE_IDS if rid in applicable_rule_ids(content_type)]
    if verify_facts and fact_rule_ids and verification_requires_rule_recheck(verification_results):
        _emit_progress(progress_callback, "ADJUDICATING", "正在复核事实敏感规则")
        t0 = time.perf_counter()
        logger.info("[review] fact_sensitive_recheck start rules=%s", fact_rule_ids)
        try:
            subset = await asyncio.wait_for(
                evaluate_rule_subset(article, content_type, verification_context, fact_rule_ids),
                timeout=settings.llm_adjudicator_stage_timeout_seconds,
            )
            eval_result = merge_rule_subset(eval_result, subset, fact_rule_ids)
            logger.info("[review] fact_sensitive_recheck done elapsed=%.2fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("[review] fact_sensitive_recheck degraded elapsed=%.2fs error=%s", time.perf_counter() - t0, exc)
    elif verify_facts:
        logger.info("[review] fact_sensitive_recheck skipped: no material adverse verification signal")

    validate_eval(eval_result, content_type, allow_derived_missing=True)

    if eval_result.get("unresolved_rules", []):
        _emit_progress(progress_callback, "ADJUDICATING", "正在复核未决规则")
    t0 = time.perf_counter()
    logger.info(
        "[review] adjudicate_unresolved start unresolved=%d",
        len(eval_result.get("unresolved_rules", [])),
    )
    if eval_result.get("unresolved_rules", []):
        try:
            eval_result = await asyncio.wait_for(
                adjudicate_unresolved(article, content_type, eval_result, verification_context),
                timeout=settings.llm_adjudicator_stage_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("[review] adjudicate_unresolved timeout; preserving UNRESOLVED without blocking")
    else:
        eval_result = await adjudicate_unresolved(
            article, content_type, eval_result, verification_context
        )
    logger.info(
        "[review] adjudicate_unresolved done elapsed=%.2fs unresolved=%d failed_ids=%s unresolved_ids=%s",
        time.perf_counter() - t0,
        len(eval_result.get("unresolved_rules", [])),
        [x.get("rule_id") for x in eval_result.get("failed_rules", [])],
        [x.get("rule_id") for x in eval_result.get("unresolved_rules", [])],
    )
    validate_eval(eval_result, content_type, allow_derived_missing=True)

    # FINAL meta rules are derived from the already-confirmed Rule state. They never
    # get a fresh model judgement and never create standalone author feedback.
    eval_result = derive_meta_rules(eval_result, content_type)
    validate_eval(eval_result, content_type)
    logger.info(
        "[review] rule_results final failed_ids=%s unresolved_ids=%s",
        [x.get("rule_id") for x in eval_result.get("failed_rules", [])],
        [x.get("rule_id") for x in eval_result.get("unresolved_rules", [])],
    )

    # After Rule FAIL is finalized, three independent downstream tasks run in parallel:
    # 1) cluster same-source author problems; 2) assess dimension impact and derive the
    # release state; 3) extract strengths. No downstream task may alter Rule results.
    secondary_timeout = settings.llm_secondary_timeout_seconds

    async def _strength_stage():
        t = time.perf_counter()
        logger.info("[review] extract_strengths start model=%s timeout=%.0fs", settings.llm_model_secondary or settings.llm_model, secondary_timeout)
        try:
            value = await asyncio.wait_for(
                extract_strengths(article, content_type, eval_result),
                timeout=secondary_timeout + 5,
            )
            logger.info("[review] extract_strengths done elapsed=%.2fs strengths=%d", time.perf_counter() - t, len(value))
            return value
        except Exception as exc:
            logger.warning("[review] extract_strengths degraded elapsed=%.2fs error=%s", time.perf_counter() - t, exc)
            return []

    async def _feedback_stage():
        t = time.perf_counter()
        logger.info("[review] problem_clusterer start model=%s timeout=%.0fs", settings.llm_model_secondary or settings.llm_model, secondary_timeout)
        try:
            value = await asyncio.wait_for(
                compose_feedback(article, eval_result, verification_context.results),
                timeout=secondary_timeout + 5,
            )
            logger.info("[review] problem_clusterer done elapsed=%.2fs issues=%d", time.perf_counter() - t, len(value.get("issue_candidates", [])))
            return value
        except Exception as exc:
            logger.warning("[review] problem_clusterer degraded elapsed=%.2fs error=%s", time.perf_counter() - t, exc)
            return deterministic_feedback_fallback(eval_result)

    async def _dimension_stage():
        t = time.perf_counter()
        ctx = dimension_fail_context(eval_result)
        logger.info(
            "[review] dimension_gate start model=%s timeout=%.0fs input_failed_ids=%s",
            settings.llm_model_secondary or settings.llm_model,
            secondary_timeout,
            [x.get("rule_id") for x in ctx],
        )
        try:
            value = await asyncio.wait_for(
                evaluate_dimensions_and_gate(article, content_type, eval_result),
                timeout=secondary_timeout + 5,
            )
            logger.info(
                "[review] dimension_gate done elapsed=%.2fs final=%s states=%s",
                time.perf_counter() - t,
                value.get("final_judgement"),
                value.get("dimension_states"),
            )
            return value
        except Exception as exc:
            logger.warning("[review] dimension_gate degraded elapsed=%.2fs error=%s", time.perf_counter() - t, exc)
            value = deterministic_dimension_fallback(eval_result)
            logger.info("[review] dimension_gate fallback final=%s states=%s", value["final_judgement"], value["dimension_states"])
            return value

    _emit_progress(progress_callback, "POSTPROCESSING", "正在并行整理问题、判断五维与提取值得保留")
    t0 = time.perf_counter()
    logger.info("[review] postprocess_parallel start")
    strengths, feedback, dimension_result = await asyncio.gather(
        _strength_stage(), _feedback_stage(), _dimension_stage()
    )
    logger.info("[review] postprocess_parallel done elapsed=%.2fs", time.perf_counter() - t0)

    # Gate has no independent editorial logic. Release state is a deterministic
    # projection of Dimension: all dimensions 达标 => 可以继续; otherwise 需要修改.
    dimension_states = dimension_result["dimension_states"]
    final_judgement = dimension_result["final_judgement"]

    # Product consistency invariant: a blocked finished draft must expose at least one
    # Rule-grounded issue. If the model clusterer returned none, deterministic clusters
    # are used rather than showing "需要修改" with an empty issue list.
    if final_judgement == "需要修改" and not feedback.get("issue_candidates"):
        feedback = deterministic_feedback_fallback(eval_result)

    # Positive feedback is produced by its own PASS-grounded extractor, never by the
    # negative Feedback Composer. It cannot change Gate/final judgement.
    feedback["strengths"] = strengths

    core = feedback.get("core_diagnosis")
    core_text = core.get("text") if isinstance(core, dict) else None

    result = {
        "review_id": str(uuid.uuid4()),
        "content_type": content_type,
        "final_judgement": final_judgement,
        "dimension_states": dimension_states,
        "core_diagnosis": core_text,
        "issues": feedback.get("issue_candidates", []),
        "strengths": feedback.get("strengths", []),
        "unresolved_rules": eval_result.get("unresolved_rules", []),
        "failed_rule_ids": [x.get("rule_id") for x in eval_result.get("failed_rules", [])],
        "model_provider": settings.llm_provider,
        "model": settings.llm_model or "mock",
        "registry_hash": registry_hash(),
        "verification_note": verification_note,
        "verification_state": verification_context.state,
        "verification_results": verification_context.results,
    }

    _emit_progress(progress_callback, "COMPLETED", "审核完成")
    logger.info(
        "[review] complete elapsed=%.2fs final=%s issues=%d strengths=%d",
        time.perf_counter() - review_started,
        result["final_judgement"],
        len(result["issues"]),
        len(result["strengths"]),
    )
    return result
