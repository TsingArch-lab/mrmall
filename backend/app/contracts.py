from __future__ import annotations

import json
import re
from typing import Any

VALID_TYPES = {"A", "B", "C", "D", "E"}


class ContractError(ValueError):
    pass


def _unwrap_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Unwrap common harmless wrapper objects returned by LLMs."""
    cur = data
    for _ in range(3):
        if any(k in cur for k in ("content_type", "passed_rule_ids", "failed_rules", "final_judgement")):
            return cur
        found = None
        for key in ("result", "data", "output", "response", "classification"):
            value = cur.get(key)
            if isinstance(value, dict):
                found = value
                break
        if found is None:
            return cur
        cur = found
    return cur


def normalize_content_type(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("content_type", "type", "article_type", "category", "label"):
            if key in value:
                value = value[key]
                break
    text = str(value).strip().upper()

    # Exact and common forms: D / D类 / 类型D / TYPE D.
    m = re.search(r"(?:类型\s*|TYPE\s*)?([A-E])(?:\s*类)?", text)
    if m:
        return m.group(1)

    # Chinese semantic labels as a bounded compatibility map.
    aliases = {
        "企业/项目深度分析稿": "A",
        "企业项目深度分析稿": "A",
        "企业/项目深度分析": "A",
        "行业现象/趋势分析稿": "B",
        "行业现象趋势分析稿": "B",
        "行业现象/趋势分析": "B",
        "数据/研究解读稿": "C",
        "数据研究解读稿": "C",
        "数据/研究解读": "C",
        "内省/态度声明稿": "D",
        "内省态度声明稿": "D",
        "内省/态度声明": "D",
        "信息汇总型": "E",
        "信息汇总": "E",
    }
    for label, code in aliases.items():
        if label.upper() in text:
            return code
    return None


def normalize_router(data: dict[str, Any]) -> dict[str, Any]:
    d = _unwrap_dict(data)
    raw_type = None
    for key in ("content_type", "type", "article_type", "category", "label"):
        if key in d:
            raw_type = d[key]
            break
    ctype = normalize_content_type(raw_type)
    if ctype not in VALID_TYPES:
        raise ContractError(f"router missing/invalid content_type; received keys={sorted(d.keys())}")

    confidence = d.get("confidence", d.get("score", 0.0))
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    primary_value = d.get("primary_value", d.get("reason", d.get("value_source", "")))
    if not isinstance(primary_value, str):
        primary_value = str(primary_value or "")

    return {
        "content_type": ctype,
        "confidence": confidence,
        "primary_value": primary_value[:500],
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def normalize_rule_evaluation(
    data: dict[str, Any],
    *,
    content_type: str,
    supplied_rule_ids: list[str],
    verification_context=None,
) -> dict[str, Any]:
    d = _unwrap_dict(data)
    supplied = set(supplied_rule_ids)

    passed = _string_list(d.get("passed_rule_ids", d.get("pass_rule_ids", d.get("passed", []))))
    na_ids = _string_list(d.get("na_rule_ids", d.get("not_applicable_rule_ids", d.get("na", []))))

    failed_raw = d.get("failed_rules", d.get("fails", d.get("failed", [])))
    if failed_raw is None:
        failed_raw = []
    if isinstance(failed_raw, dict):
        failed_raw = [failed_raw]
    failed = []
    if isinstance(failed_raw, list):
        for item in failed_raw:
            if isinstance(item, str):
                failed.append({
                    "rule_id": item,
                    "article_evidence": [],
                    "match_explanation": "",
                })
                continue
            if not isinstance(item, dict):
                continue
            rid = item.get("rule_id", item.get("id"))
            evidence = item.get("article_evidence", item.get("evidence", item.get("quotes", [])))
            explanation = item.get("match_explanation", item.get("explanation", item.get("reason", "")))
            failed.append({
                "rule_id": str(rid or "").strip(),
                "article_evidence": _string_list(evidence),
                "match_explanation": str(explanation or "").strip(),
            })

    unresolved_raw = d.get("unresolved_rules", d.get("unresolved", []))
    if unresolved_raw is None:
        unresolved_raw = []
    if isinstance(unresolved_raw, dict):
        unresolved_raw = [unresolved_raw]
    unresolved = []
    if isinstance(unresolved_raw, list):
        for item in unresolved_raw:
            if isinstance(item, str):
                unresolved.append({"rule_id": item, "why_unresolved": "模型未提供原因"})
            elif isinstance(item, dict):
                unresolved.append({
                    "rule_id": str(item.get("rule_id", item.get("id", ""))).strip(),
                    "why_unresolved": str(item.get("why_unresolved", item.get("reason", ""))).strip()
                    or "模型未提供原因",
                })

    # If a model omitted evaluated_rule_ids but status buckets are otherwise valid,
    # derive it deterministically from the supplied set. It carries no judgement semantics.
    evaluated = _string_list(d.get("evaluated_rule_ids"))
    if not evaluated:
        evaluated = list(supplied_rule_ids)

    # Normalize content type from response but never let it override the runtime's known type.
    response_type = normalize_content_type(d.get("content_type")) or content_type
    if response_type != content_type:
        raise ContractError(f"rule evaluator changed content_type from {content_type} to {response_type}")

    if verification_context is not None:
        from .verification import fail_is_only_unverified
        kept_failed = []
        guarded_unresolved = list(unresolved)
        for item in failed:
            if fail_is_only_unverified(item["rule_id"], item.get("match_explanation", ""), verification_context):
                guarded_unresolved.append({
                    "rule_id": item["rule_id"],
                    "why_unresolved": "外部事实核验未执行；仅凭‘无法核实/缺乏来源’不能判定该 Rule FAIL。",
                })
            else:
                kept_failed.append(item)
        failed = kept_failed
        unresolved = guarded_unresolved

    result = {
        "content_type": content_type,
        "evaluated_rule_ids": evaluated,
        "passed_rule_ids": passed,
        "failed_rules": failed,
        "na_rule_ids": na_ids,
        "unresolved_rules": unresolved,
    }

    # Contract-level checks before runtime provenance checks.
    for rid in passed + na_ids:
        if rid not in supplied:
            raise ContractError(f"unknown Rule ID in evaluator output: {rid}")
    for item in failed:
        if item["rule_id"] not in supplied:
            raise ContractError(f"unknown FAIL Rule ID: {item['rule_id']}")
        if not item["article_evidence"]:
            raise ContractError(f"FAIL {item['rule_id']} missing article_evidence")
        if not item["match_explanation"]:
            raise ContractError(f"FAIL {item['rule_id']} missing match_explanation")
    for item in unresolved:
        if item["rule_id"] not in supplied:
            raise ContractError(f"unknown UNRESOLVED Rule ID: {item['rule_id']}")

    buckets = passed + na_ids + [x["rule_id"] for x in failed] + [x["rule_id"] for x in unresolved]
    if len(buckets) != len(set(buckets)):
        raise ContractError("a Rule appears in multiple evaluator status buckets")
    missing = supplied - set(buckets)
    if missing:
        raise ContractError(f"evaluator omitted Rule IDs: {sorted(missing)}")

    return result


def normalize_feedback(data: dict[str, Any]) -> dict[str, Any]:
    d = _unwrap_dict(data)
    final = d.get("final_judgement", d.get("judgement", d.get("status")))
    dims = d.get("dimension_assessments", d.get("dimension_states", {}))
    core = d.get("core_diagnosis")
    issues = d.get("issue_candidates", d.get("issues", []))
    strengths = d.get("strengths", d.get("keep", []))

    if isinstance(core, str):
        # A string has no provenance. Keep it invalid; caller will use deterministic fallback.
        core = {"text": core, "supporting_rule_ids": [], "article_evidence": []}
    if issues is None:
        issues = []
    if isinstance(issues, dict):
        issues = [issues]
    if strengths is None:
        strengths = []

    return {
        "final_judgement": final,
        "dimension_assessments": dims if isinstance(dims, dict) else {},
        "core_diagnosis": core,
        "issue_candidates": issues if isinstance(issues, list) else [],
        "strengths": _string_list(strengths),
    }
