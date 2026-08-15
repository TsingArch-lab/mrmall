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

DIM_MAP = {
    "TOPIC": "选题价值",
    "EVIDENCE": "证据支撑",
    "GLOBAL": "证据支撑",
    "INSIGHT": "观点质量",
    "STRUCTURE": "结构逻辑",
    "EXPRESSION": "表达质量",
    "FINAL": "表达质量",
}


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
    return [{k: reg[rid].get(k) for k in keys} for rid in applicable_rule_ids(content_type)]


def validate_eval(result: dict[str, Any], content_type: str):
    supplied = set(applicable_rule_ids(content_type))
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
    provider = get_provider()
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
        "你是严格的 RULE_BATCH_EVALUATOR。只能执行输入 Rules，必须严格按指定 JSON 契约输出。",
        user,
        reasoning_effort="max",
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
    provider = get_provider()
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

    provider = get_provider()
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


def aggregate(eval_result: dict[str, Any]):
    reg = rules_by_id()
    fails = eval_result.get("failed_rules", [])
    fail_ids = [x["rule_id"] for x in fails]
    by_stage: dict[str, list[dict[str, Any]]] = {}
    for rid in fail_ids:
        r = reg[rid]
        by_stage.setdefault(r["stage"], []).append(r)

    revise = False
    if any(reg[rid]["severity"] == "BLOCKER" for rid in fail_ids):
        revise = True
    if eval_result["content_type"] in {"A", "B"} and len(by_stage.get("TOPIC", [])) >= 2:
        revise = True
    for stage in ["STRUCTURE", "FINAL"]:
        if sum(1 for r in by_stage.get(stage, []) if r["severity"] == "MAJOR") >= 3:
            revise = True

    final = "需要修改" if revise else "可以继续"
    dims = {
        k: "达标"
        for k in ["选题价值", "证据支撑", "观点质量", "结构逻辑", "表达质量"]
    }
    for rid in fail_ids:
        stage = reg[rid]["stage"]
        dim = DIM_MAP.get(stage)
        if dim:
            dims[dim] = "有明显问题"
    return {
        "final_judgement": final,
        "dimension_states": dims,
        "failed_rule_ids": fail_ids,
    }


def validate_feedback(
    feedback: dict[str, Any],
    eval_result: dict[str, Any],
    expected_final: str,
):
    failed = {x["rule_id"] for x in eval_result.get("failed_rules", [])}

    if feedback.get("final_judgement") != expected_final:
        raise ValueError("Feedback Composer attempted to change deterministic final_judgement")

    core = feedback.get("core_diagnosis")
    issues = feedback.get("issue_candidates", [])
    negative = ([core] if core else []) + issues

    if not failed and negative:
        raise ValueError(
            "No Rule, No Feedback violation: negative feedback exists with zero FAIL Rules"
        )

    for item in negative:
        if not isinstance(item, dict):
            raise ValueError("Feedback negative item must be an object")
        support = set(item.get("supporting_rule_ids", []))
        if not support or not support.issubset(failed):
            raise ValueError(
                f"Feedback provenance violation: {support} is not subset of FAIL Rules {failed}"
            )
        evidence = item.get("article_evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Feedback item missing article evidence")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError("Feedback item missing text")


def deterministic_feedback_fallback(
    eval_result: dict[str, Any],
    agg: dict[str, Any],
) -> dict[str, Any]:
    """Fail-safe author feedback using only validated FAIL Rule payloads.

    This keeps the site usable if a provider cannot follow the Feedback JSON contract,
    without allowing the program to invent new editorial standards.
    """
    failed = eval_result.get("failed_rules", [])
    if not failed:
        return {
            "final_judgement": agg["final_judgement"],
            "dimension_assessments": agg["dimension_states"],
            "core_diagnosis": None,
            "issue_candidates": [],
            "strengths": [],
        }

    reg = rules_by_id()
    severity_order = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3, "NA": 4}
    ordered = sorted(
        failed,
        key=lambda x: severity_order.get(reg[x["rule_id"]].get("severity", "INFO"), 9),
    )

    issues = []
    for item in ordered:
        rid = item["rule_id"]
        rule = reg[rid]
        issues.append(
            {
                "text": f"{rule['name']}：{item['match_explanation']}",
                "supporting_rule_ids": [rid],
                "article_evidence": item["article_evidence"],
            }
        )

    first = issues[0]
    return {
        "final_judgement": agg["final_judgement"],
        "dimension_assessments": agg["dimension_states"],
        "core_diagnosis": {
            "text": first["text"],
            "supporting_rule_ids": first["supporting_rule_ids"],
            "article_evidence": first["article_evidence"],
        },
        "issue_candidates": issues,
        "strengths": [],
    }


async def extract_strengths(
    article: str,
    content_type: str,
    eval_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract positive author feedback from selected PASS Rules only.

    This is intentionally separate from negative feedback composition so a model cannot
    turn free-form praise into a new editorial standard or influence Gate results.
    """
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
            # PASS is necessary but not sufficient: at least one supporting Rule must be
            # an anchor capable of representing a distinctive content asset. Evidence-only
            # or merely "no-error" PASS states cannot generate praise.
            if not (set(support) & STRENGTH_ANCHOR_RULE_IDS):
                continue
            # Positive provenance is stricter than negative prose: every cited excerpt
            # must literally occur in the submitted article after trimming.
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


async def compose_feedback(
    eval_result: dict[str, Any],
    agg: dict[str, Any],
    verification_results: list[dict[str, Any]],
):
    failed = eval_result.get("failed_rules", [])
    if not failed:
        return deterministic_feedback_fallback(eval_result, agg)

    reg = rules_by_id()
    clusters = cluster_failed_rules(failed, reg)
    if not clusters:
        return {"final_judgement":agg["final_judgement"],"dimension_assessments":agg["dimension_states"],"core_diagnosis":None,"issue_candidates":[],"strengths":[]}

    provider = get_provider(secondary=True)
    prompt = (PROMPTS / "02_feedback_composer.md").read_text(encoding="utf-8")
    user = _render(prompt, {"FINAL_JUDGEMENT":agg["final_judgement"],"DIMENSION_STATES":agg["dimension_states"],"FAILED_RULES_ONLY":failed,"FAILED_RULE_CLUSTERS":clusters,"VERIFICATION_RESULTS":verification_results,"PASSED_STRENGTH_CANDIDATES":[]})
    try:
        raw = await provider.generate_json("你是 FEEDBACK_COMPOSER。不得新增审稿标准；不得修改程序最终判断。作者端优先按 FAILED_RULE_CLUSTERS 合并同源问题；不得一 Rule 一问题；不得把 Gate 后果、severity 或 BLOCKER 本身写成独立问题。", user)
        feedback = normalize_feedback(raw)
        feedback["final_judgement"] = agg["final_judgement"]
        feedback["dimension_assessments"] = agg["dimension_states"]
        validate_feedback(feedback, eval_result, agg["final_judgement"])
        return feedback
    except Exception as exc:
        logger.warning("Feedback Composer failed; clustered fallback: %s", exc)
        issues=[]
        for c in clusters:
            ids=c["supporting_rule_ids"]; ev=c["article_evidence"]
            if len(ids)==1:
                rid=ids[0]; f=next(x for x in failed if x["rule_id"]==rid); text=f"{reg[rid]['name']}：{f['match_explanation']}"
            else:
                text=f"{c['cluster_hint']}：多个已 FAIL Rules 指向同一上游问题。"
            issues.append({"text":text,"supporting_rule_ids":ids,"article_evidence":ev})
        return {"final_judgement":agg["final_judgement"],"dimension_assessments":agg["dimension_states"],"core_diagnosis":issues[0] if issues else None,"issue_candidates":issues,"strengths":[]}

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
    validate_eval(eval_result, content_type)

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

    validate_eval(eval_result, content_type)

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
        "[review] adjudicate_unresolved done elapsed=%.2fs unresolved=%d",
        time.perf_counter() - t0,
        len(eval_result.get("unresolved_rules", [])),
    )
    validate_eval(eval_result, content_type)

    _emit_progress(progress_callback, "AGGREGATING", "正在汇总规则结果")
    t0 = time.perf_counter()
    logger.info("[review] aggregate start")
    agg = aggregate(eval_result)
    logger.info(
        "[review] aggregate done elapsed=%.2fs final=%s failed=%d",
        time.perf_counter() - t0,
        agg["final_judgement"],
        len(agg["failed_rule_ids"]),
    )

    # Strength extraction and feedback composition depend on the same completed Rule
    # evaluation but not on each other. Run them concurrently. Both are non-gating:
    # timeout/failure must never alter Rule results, Gate aggregation or final judgement.
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
        logger.info("[review] compose_feedback start model=%s timeout=%.0fs", settings.llm_model_secondary or settings.llm_model, secondary_timeout)
        try:
            value = await asyncio.wait_for(
                compose_feedback(eval_result, agg, verification_context.results),
                timeout=secondary_timeout + 5,
            )
            logger.info("[review] compose_feedback done elapsed=%.2fs issues=%d", time.perf_counter() - t, len(value.get("issue_candidates", [])))
            return value
        except Exception as exc:
            logger.warning("[review] compose_feedback degraded elapsed=%.2fs error=%s", time.perf_counter() - t, exc)
            return deterministic_feedback_fallback(eval_result, agg)

    _emit_progress(progress_callback, "POSTPROCESSING", "正在整理问题清单与值得保留")
    t0 = time.perf_counter()
    logger.info("[review] postprocess_parallel start")
    strengths, feedback = await asyncio.gather(_strength_stage(), _feedback_stage())
    logger.info("[review] postprocess_parallel done elapsed=%.2fs", time.perf_counter() - t0)

    # Positive feedback is produced by its own PASS-grounded extractor, never by the
    # negative Feedback Composer. It cannot change Gate/final judgement.
    feedback["strengths"] = strengths

    core = feedback.get("core_diagnosis")
    core_text = core.get("text") if isinstance(core, dict) else None

    result = {
        "review_id": str(uuid.uuid4()),
        "content_type": content_type,
        "final_judgement": agg["final_judgement"],
        "dimension_states": agg["dimension_states"],
        "core_diagnosis": core_text,
        "issues": feedback.get("issue_candidates", []),
        "strengths": feedback.get("strengths", []),
        "unresolved_rules": eval_result.get("unresolved_rules", []),
        "failed_rule_ids": agg["failed_rule_ids"],
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
