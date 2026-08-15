from __future__ import annotations

import asyncio
import logging
import re
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

_HEADING_RE = re.compile(
    r"^(?:part\s*\d+\b|第[一二三四五六七八九十百0-9]+[章节部分]|[一二三四五六七八九十]+[、.]|\d+[.、)]|总结\b|结语\b|结论\b)",
    re.IGNORECASE,
)


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


def _normalize_newlines(article: str) -> str:
    return article.replace("\r\n", "\n").replace("\r", "\n").strip()


def _is_heading(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if len(s) <= 70 and _HEADING_RE.search(s):
        return True
    # Short standalone labels ending with a colon are often section labels.
    if len(s) <= 40 and (s.endswith(":") or s.endswith("：")):
        return True
    return False


def build_argument_blocks(article: str, max_blocks: int | None = None) -> list[dict[str, Any]]:
    """Deterministically preserve the article's real paragraph-level argument grain.

    No semantic merging is allowed. A heading may be attached to the immediately following
    paragraph only as presentation metadata; distinct prose paragraphs remain distinct blocks.
    Long paragraphs are split only by character safety, never because they seem semantically alike.
    """
    text = _normalize_newlines(article)
    if not text:
        return []

    # Blank lines are the primary author-authored paragraph boundary. If the pasted article has
    # only single newlines, retain each non-empty line as a paragraph rather than semantically
    # collapsing it.
    raw_parts = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(raw_parts) <= 2 and text.count("\n") >= 3:
        raw_parts = [p.strip() for p in text.split("\n") if p.strip()]

    paragraphs: list[dict[str, str]] = []
    for part in raw_parts:
        # Preserve internal line breaks in a paragraph, but assign an exact P id.
        paragraphs.append({"paragraph_id": f"P{len(paragraphs)+1:03d}", "text": part})

    blocks: list[dict[str, Any]] = []
    pending_heading = ""
    pending_heading_pid = ""
    hard_cap = max_blocks or max(settings.article_map_max_units, 40)

    for para in paragraphs:
        pid, ptext = para["paragraph_id"], para["text"]
        if _is_heading(ptext):
            # A heading is metadata for the next prose block. If another heading follows, keep
            # the previous one as its own block so source order is never lost.
            if pending_heading:
                blocks.append({
                    "block_id": f"B{len(blocks)+1:02d}",
                    "paragraph_ids": [pending_heading_pid],
                    "heading": pending_heading,
                    "text": pending_heading,
                })
            pending_heading, pending_heading_pid = ptext, pid
            continue

        # Very long pasted paragraphs are split by sentence boundary for model tractability.
        # This is mechanical length control, not semantic compression.
        chunks = [ptext]
        if len(ptext) > 1400:
            sentences = re.split(r"(?<=[。！？!?])", ptext)
            chunks, buf = [], ""
            for sent in sentences:
                if buf and len(buf) + len(sent) > 900:
                    chunks.append(buf.strip())
                    buf = sent
                else:
                    buf += sent
            if buf.strip():
                chunks.append(buf.strip())

        for ci, chunk in enumerate(chunks):
            pids = [pid]
            heading = ""
            if pending_heading and ci == 0:
                heading = pending_heading
                pids = [pending_heading_pid, pid]
                pending_heading = pending_heading_pid = ""
            blocks.append({
                "block_id": f"B{len(blocks)+1:02d}",
                "paragraph_ids": pids,
                "heading": heading,
                "text": chunk,
            })

    if pending_heading:
        blocks.append({
            "block_id": f"B{len(blocks)+1:02d}",
            "paragraph_ids": [pending_heading_pid],
            "heading": pending_heading,
            "text": pending_heading,
        })

    # Do not silently throw away late-article blocks. If an extreme input exceeds the safety cap,
    # coarsen only by deterministic adjacent batching and expose every source paragraph id.
    if len(blocks) > hard_cap:
        batch_size = (len(blocks) + hard_cap - 1) // hard_cap
        compacted: list[dict[str, Any]] = []
        for i in range(0, len(blocks), batch_size):
            group = blocks[i:i + batch_size]
            compacted.append({
                "block_id": f"B{len(compacted)+1:02d}",
                "paragraph_ids": [pid for b in group for pid in b["paragraph_ids"]],
                "heading": group[0].get("heading", ""),
                "text": "\n\n".join(b["text"] for b in group),
            })
        blocks = compacted

    return blocks


def serialize_argument_blocks(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        pids = ",".join(block.get("paragraph_ids", []))
        heading = block.get("heading", "")
        lines.append(f"[{block['block_id']}] paragraphs={pids}" + (f" heading={heading}" if heading else ""))
        lines.append(block.get("text", ""))
        lines.append("")
    return "\n".join(lines).strip()


def normalize_article_map(raw: dict[str, Any], article: str, blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Normalize a descriptive map. This function performs no quality judgement."""
    blocks = blocks or build_argument_blocks(article)
    block_lookup = {b["block_id"]: b for b in blocks}
    units_raw = raw.get("units", []) if isinstance(raw, dict) else []
    raw_lookup: dict[str, dict[str, Any]] = {}
    if isinstance(units_raw, list):
        for item in units_raw:
            if isinstance(item, dict):
                bid = _clean_text(item.get("block_id") or item.get("unit_id"), 20)
                if bid in block_lookup and bid not in raw_lookup:
                    raw_lookup[bid] = item

    units: list[dict[str, Any]] = []
    # One source block -> one map unit. Missing LLM labels degrade to neutral descriptors instead
    # of allowing a block to disappear from the representation.
    for idx, block in enumerate(blocks, start=1):
        bid = block["block_id"]
        item = raw_lookup.get(bid, {})
        role = _clean_text(item.get("role"), 40).lower()
        relation = _clean_text(item.get("relation_to_prior"), 40).lower()
        if role not in VALID_ROLES:
            role = "other"
        if relation not in VALID_RELATIONS:
            relation = "opens" if idx == 1 else "other"
        if idx == 1:
            relation = "opens"
        quote = _clean_text(item.get("anchor_quote"), 360)
        # Quote must exist inside this exact block, not merely somewhere else in the article.
        if quote and quote not in block["text"] and quote not in block.get("heading", ""):
            quote = ""
        if not quote:
            quote = block["text"][:180]
        ev = item.get("evidence_used", [])
        if not isinstance(ev, list):
            ev = []
        units.append({
            "unit_id": f"U{idx:02d}",
            "block_id": bid,
            "paragraph_ids": list(block.get("paragraph_ids", [])),
            "heading": _clean_text(block.get("heading") or item.get("heading"), 120),
            "source_excerpt": _clean_text(block.get("text"), 240),
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
        "representation_grain": "DETERMINISTIC_ARGUMENT_BLOCKS",
        "source_block_count": len(blocks),
        "units": units,
    }


def unavailable_article_map(reason: str = "") -> dict[str, Any]:
    return {
        "state": "NOT_RUN",
        "core_question": "",
        "thesis": "",
        "representation_grain": "NONE",
        "source_block_count": 0,
        "units": [],
        "note": reason[:500],
    }


async def build_article_representation(article: str, include_fact_claims: bool) -> ArticleRepresentation:
    prompt = PROMPT.read_text(encoding="utf-8")
    blocks = build_argument_blocks(article)
    user = _render(prompt, {
        "MAX_UNITS": len(blocks),
        "MAX_FACT_CLAIMS": settings.fact_search_max_claims,
        "INCLUDE_FACT_CLAIMS": "true" if include_fact_claims else "false",
        "ARGUMENT_BLOCKS": serialize_argument_blocks(blocks),
    })
    system = (
        "你是 ARTICLE_MAP_BUILDER。只对程序已切好的 Argument Blocks 做描述性标注；"
        "不得合并、删除或重排任何 Block；不是审稿人，不做PASS/FAIL，不得创建规则或评价标准。"
        "严格按用户消息中的JSON结构输出。"
    )
    raw = await asyncio.wait_for(
        get_provider(secondary=True).generate_json(system, user),
        timeout=settings.article_map_timeout_seconds,
    )
    article_map = normalize_article_map(raw, article, blocks=blocks)
    fact_claims = raw.get("fact_claims", []) if isinstance(raw, dict) else []
    if not include_fact_claims or not isinstance(fact_claims, list):
        fact_claims = []
    return ArticleRepresentation(
        state="READY",
        article_map=article_map,
        fact_claims=[x for x in fact_claims if isinstance(x, dict)],
        note=(
            f"Argument Map 已生成，共 {len(article_map.get('units', []))} 个保真论证块；"
            "每个程序切分 Block 均被保留。"
        ),
    )
