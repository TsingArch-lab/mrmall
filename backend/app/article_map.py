from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import CORE_DIR, settings
from .llm import get_provider

logger = logging.getLogger("mall_content_os.article_map")
PROMPT = CORE_DIR / "portable" / "prompts" / "00_article_map_builder.md"

VALID_ROLES = {
    "opening", "background", "case", "evidence", "mechanism", "comparison",
    "inference", "summary", "transition", "conclusion", "other",
}
VALID_RELATIONS = {
    "opens", "adds_example", "adds_mechanism", "adds_condition", "adds_comparison",
    "adds_result", "synthesizes", "restates", "transitions", "shifts_topic", "other",
}


@dataclass(frozen=True)
class ArticleRepresentation:
    state: str
    article_map: dict[str, Any]
    fact_claims: list[dict[str, Any]]
    note: str = ""


def _render(template: str, values: dict[str, Any]) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def _clean_text(value: Any, max_chars: int) -> str:
    return str(value or "").strip()[:max_chars]


def normalize_article_map(raw: dict[str, Any], article: str) -> dict[str, Any]:
    """Normalize a descriptive map. This function performs no quality judgement."""
    units_raw = raw.get("units", []) if isinstance(raw, dict) else []
    units: list[dict[str, Any]] = []
    if isinstance(units_raw, list):
        for idx, item in enumerate(units_raw[: settings.article_map_max_units], start=1):
            if not isinstance(item, dict):
                continue
            role = _clean_text(item.get("role"), 40).lower()
            relation = _clean_text(item.get("relation_to_prior"), 40).lower()
            if role not in VALID_ROLES:
                role = "other"
            if relation not in VALID_RELATIONS:
                relation = "opens" if not units else "other"
            if not units:
                relation = "opens"
            quote = _clean_text(item.get("anchor_quote"), 360)
            # Exact article provenance only. A hallucinated quote is discarded rather than
            # becoming evidence for a downstream Rule.
            if quote and quote not in article:
                quote = ""
            ev = item.get("evidence_used", [])
            if not isinstance(ev, list):
                ev = []
            units.append({
                "unit_id": f"U{len(units)+1:02d}",
                "heading": _clean_text(item.get("heading"), 120),
                "anchor_quote": quote,
                "role": role,
                "main_claim": _clean_text(item.get("main_claim"), 420),
                "evidence_used": [_clean_text(x, 220) for x in ev[:5] if _clean_text(x, 220)],
                "mechanism": _clean_text(item.get("mechanism"), 420),
                "relation_to_prior": relation,
                "new_contribution": _clean_text(item.get("new_contribution"), 420),
            })

    return {
        "state": "READY",
        "core_question": _clean_text(raw.get("core_question") if isinstance(raw, dict) else "", 600),
        "thesis": _clean_text(raw.get("thesis") if isinstance(raw, dict) else "", 600),
        "units": units,
    }


def unavailable_article_map(reason: str = "") -> dict[str, Any]:
    return {
        "state": "NOT_RUN",
        "core_question": "",
        "thesis": "",
        "units": [],
        "note": reason[:500],
    }


async def build_article_representation(article: str, include_fact_claims: bool) -> ArticleRepresentation:
    prompt = PROMPT.read_text(encoding="utf-8")
    user = _render(prompt, {
        "MAX_UNITS": settings.article_map_max_units,
        "MAX_FACT_CLAIMS": settings.fact_search_max_claims,
        "INCLUDE_FACT_CLAIMS": "true" if include_fact_claims else "false",
        "ARTICLE": article,
    })
    system = (
        "你是 ARTICLE_MAP_BUILDER。只生成描述性文章结构表示；不是审稿人，不做PASS/FAIL，"
        "不得创建规则或评价标准。严格按用户消息中的JSON结构输出。"
    )
    raw = await asyncio.wait_for(
        get_provider(secondary=True).generate_json(system, user),
        timeout=settings.article_map_timeout_seconds,
    )
    article_map = normalize_article_map(raw, article)
    fact_claims = raw.get("fact_claims", []) if isinstance(raw, dict) else []
    if not include_fact_claims or not isinstance(fact_claims, list):
        fact_claims = []
    return ArticleRepresentation(
        state="READY",
        article_map=article_map,
        fact_claims=[x for x in fact_claims if isinstance(x, dict)],
        note=f"Article Map 已生成，共 {len(article_map.get('units', []))} 个主要论证单元。",
    )
