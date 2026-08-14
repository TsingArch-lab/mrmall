from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from .config import CORE_DIR, settings
from .contracts import (
    ContractError,
    normalize_feedback,
    normalize_router,
    normalize_rule_evaluation,
)
from .llm import LLMError, get_provider

logger = logging.getLogger("mall_content_os.review")

REGISTRY = CORE_DIR / "registry" / "compiled_rule_registry.json"
GATES = CORE_DIR / "portable" / "runtime" / "gate_registry.json"
PROMPTS = CORE_DIR / "portable" / "prompts"

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


async def evaluate_rules(article: str, content_type: str, verification_results: list[dict[str, Any]]):
    provider = get_provider()
    rules = compact_rules(content_type)
    supplied_ids = [r["rule_id"] for r in rules]
    evaluator = (PROMPTS / "01_rule_batch_evaluator.md").read_text(encoding="utf-8")
    user = _render(
        evaluator,
        {
            "CONTENT_TYPE": content_type,
            "APPLICABLE_RULES_COMPACT": rules,
            "VERIFICATION_RESULTS": verification_results,
            "ARTICLE": article,
        },
    )

    raw = await provider.generate_json(
        "你是严格的 RULE_BATCH_EVALUATOR。只能执行输入 Rules，必须严格按指定 JSON 契约输出。",
        user,
    )
    try:
        return normalize_rule_evaluation(
            raw, content_type=content_type, supplied_rule_ids=supplied_ids
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
                "不得新增 Rule ID。FAIL 必须保留原输出中已有的文章证据；没有证据则转为 UNRESOLVED。"
            ),
        )
        try:
            return normalize_rule_evaluation(
                repaired, content_type=content_type, supplied_rule_ids=supplied_ids
            )
        except ContractError as exc:
            raise LLMError(
                f"Rule Evaluator 输出未通过契约校验：{exc}. "
                "为防止错误审稿，本次结果已中止。"
            ) from first_exc


async def adjudicate_unresolved(
    article: str, content_type: str, eval_result: dict[str, Any]
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
            "VERIFICATION_RESULTS": [],
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
            raw, content_type=content_type, supplied_rule_ids=unresolved_ids
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
            "strengths": ["没有触发当前 Rules 定义的阻塞性问题。"],
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


async def compose_feedback(
    eval_result: dict[str, Any],
    agg: dict[str, Any],
    verification_results: list[dict[str, Any]],
):
    failed = eval_result.get("failed_rules", [])
    if not failed:
        return deterministic_feedback_fallback(eval_result, agg)

    provider = get_provider()
    prompt = (PROMPTS / "02_feedback_composer.md").read_text(encoding="utf-8")
    user = _render(
        prompt,
        {
            "FINAL_JUDGEMENT": agg["final_judgement"],
            "DIMENSION_STATES": agg["dimension_states"],
            "FAILED_RULES_ONLY": failed,
            "VERIFICATION_RESULTS": verification_results,
            "PASSED_STRENGTH_CANDIDATES": [],
        },
    )

    try:
        raw = await provider.generate_json(
            "你是 FEEDBACK_COMPOSER。不得新增审稿标准；最终判断由程序给定，不得修改。",
            user,
        )
        feedback = normalize_feedback(raw)
        # Runtime is authoritative.
        feedback["final_judgement"] = agg["final_judgement"]
        feedback["dimension_assessments"] = agg["dimension_states"]
        validate_feedback(feedback, eval_result, agg["final_judgement"])
        return feedback
    except Exception as exc:
        logger.warning("Feedback Composer contract failed; using deterministic fallback: %s", exc)
        return deterministic_feedback_fallback(eval_result, agg)


def registry_hash():
    return load_json(REGISTRY).get("registry_semantic_hash", "unknown")


async def review_article(
    article: str, content_type: str, verify_facts: bool = False
):
    if content_type == "AUTO":
        content_type = await route_content_type(article)

    verification_note = None
    verification_results: list[dict[str, Any]] = []
    if verify_facts:
        verification_note = (
            "Web v0.1.2 尚未接入外部事实检索插件；本次不会伪造事实核验结果。"
        )

    eval_result = await evaluate_rules(article, content_type, verification_results)
    validate_eval(eval_result, content_type)

    eval_result = await adjudicate_unresolved(article, content_type, eval_result)
    validate_eval(eval_result, content_type)

    agg = aggregate(eval_result)
    feedback = await compose_feedback(eval_result, agg, verification_results)

    core = feedback.get("core_diagnosis")
    core_text = core.get("text") if isinstance(core, dict) else None

    return {
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
    }
