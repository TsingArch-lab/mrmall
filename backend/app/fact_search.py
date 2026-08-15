from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings
from .llm import get_provider

logger = logging.getLogger("mall_content_os.fact_search")

VALID_STATUSES = {
    "confirmed",
    "basically_confirmed",
    "questionable",
    "no_reliable_source",
    "contradicted",
}
VALID_TYPES = {"data", "case", "quote"}
VALID_SOURCE_LEVELS = {"primary", "authoritative_secondary", "secondary", "none"}


@dataclass(frozen=True)
class FactSearchOutcome:
    state: str
    results: list[dict[str, Any]]
    note: str
    searched_claims: int = 0


def _search_key() -> str:
    return (settings.fact_search_api_key or "").strip()


def fact_search_available() -> bool:
    return settings.fact_search_provider.lower().strip() == "tavily" and bool(_search_key())


async def _extract_claims(article: str, content_type: str) -> list[dict[str, Any]]:
    system = """你是 FACT_CLAIM_EXTRACTOR。你的唯一任务是从文章中挑选最值得联网核验的客观事实声明。
严格边界：
1. 只提取客观可核验事实：精确数字、时间地点面积金额排名、开关店/进驻/改造事件、人物身份、项目空间事实、历史事实、首个/最大/唯一/第一，以及明确归属于报告/机构/人物的外部观点或引语。
2. 不提取作者自己的分析、因果判断、价值判断、趋势推论，不得为作者观点寻找支持材料。
3. 优先级：承担核心论证支点的事实 > 精确数字/极值词 > 引语/归属 > 关键时间节点。
4. 最多返回 MAX_CLAIMS 条；不要为了凑数提取普通低风险事实。
5. search_query 要适合直接送入中文互联网搜索，保留关键专名、数字、年份、报告名或人物名。
只输出 JSON：{"claims":[{"claim":"原文中的完整事实声明","type":"data|case|quote","importance":"high|medium","search_query":"搜索词"}]}。"""
    user = f"CONTENT_TYPE: {content_type}\nMAX_CLAIMS: {settings.fact_search_max_claims}\n\nARTICLE:\n{article}"
    raw = await asyncio.wait_for(
        get_provider(secondary=True).generate_json(system, user),
        timeout=settings.fact_verifier_timeout_seconds,
    )
    items = raw.get("claims", []) if isinstance(raw, dict) else []
    out: list[dict[str, Any]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        query = str(item.get("search_query", "")).strip()
        ctype = str(item.get("type", "case")).strip().lower()
        importance = str(item.get("importance", "medium")).strip().lower()
        if not claim or not query or claim in seen:
            continue
        if ctype not in VALID_TYPES:
            ctype = "case"
        if importance not in {"high", "medium"}:
            importance = "medium"
        seen.add(claim)
        out.append({"claim": claim, "type": ctype, "importance": importance, "search_query": query})
        if len(out) >= settings.fact_search_max_claims:
            break
    return out


async def _tavily_search(query: str) -> list[dict[str, Any]]:
    payload = {
        "query": query,
        "search_depth": settings.fact_search_depth,
        "chunks_per_source": 2,
        "max_results": settings.fact_search_max_results,
        "topic": "general",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_favicon": False,
    }
    headers = {
        "Authorization": f"Bearer {_search_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.fact_search_timeout_seconds) as client:
        resp = await client.post("https://api.tavily.com/search", headers=headers, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"Tavily search error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    out = []
    for r in data.get("results", [])[: settings.fact_search_max_results]:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url", "")).strip()
        title = str(r.get("title", "")).strip()
        content = str(r.get("content", "")).strip()
        if not url:
            continue
        out.append({"title": title, "url": url, "snippet": content[:1800], "score": r.get("score")})
    return out


async def _search_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, settings.fact_search_concurrency))

    async def one(idx: int, claim: dict[str, Any]):
        async with sem:
            try:
                sources = await _tavily_search(claim["search_query"])
                return idx, sources, None
            except Exception as exc:
                logger.warning("[fact-search] query failed idx=%d error=%s", idx, exc)
                return idx, [], str(exc)

    tasks = [one(i, c) for i, c in enumerate(claims)]
    gathered = await asyncio.gather(*tasks)
    enriched = [dict(c) for c in claims]
    for idx, sources, error in gathered:
        enriched[idx]["sources"] = sources
        if error:
            enriched[idx]["search_error"] = error
    return enriched


async def _classify(enriched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Claims with zero results are deterministic: no public reliable source was found in this search.
    with_sources = [x for x in enriched if x.get("sources")]
    no_sources = [x for x in enriched if not x.get("sources")]

    results: list[dict[str, Any]] = []
    for item in no_sources:
        results.append({
            "claim": item["claim"],
            "type": item["type"],
            "status": "no_reliable_source",
            "source_level": "none",
            "evidence": "本轮搜索未返回可用于核验的公开来源。",
            "notes": "未找到可靠依据不等于事实错误。" + (" 搜索服务返回错误。" if item.get("search_error") else ""),
            "sources": [],
        })

    if not with_sources:
        return results

    compact = []
    for i, item in enumerate(with_sources):
        compact.append({
            "id": i,
            "claim": item["claim"],
            "type": item["type"],
            "sources": [
                {"title": s.get("title"), "url": s.get("url"), "snippet": s.get("snippet")}
                for s in item.get("sources", [])
            ],
        })

    system = """你是 FACT_VERIFIER。只依据给你的搜索来源核验文章事实，不得使用模型记忆补充证据，也不得评价作者观点。
分类标准：
confirmed=可靠来源与文章表述基本一致；
basically_confirmed=核心事实成立，但时间/范围/数字/定语有轻微偏差；
questionable=相关来源不足以支持当前说法，或可靠来源之间存在冲突；
no_reliable_source=没有足够可靠的公开来源；
contradicted=可靠来源与文章表述直接冲突。
source_level: primary=官方/政府/交易所/企业原始资料；authoritative_secondary=权威媒体/研究机构；secondary=一般可靠二手；none=无。
重要：搜索摘要只能支持摘要明确写出的内容；不要把“没搜到”写成“错误”。
只输出 JSON：{"results":[{"id":0,"status":"...","source_level":"...","evidence":"简洁说明来源支持/冲突的具体点","notes":"必要时说明口径或局限","source_indices":[0,1]}]}。"""
    user = "SEARCH_EVIDENCE:\n" + json.dumps(compact, ensure_ascii=False)
    try:
        raw = await asyncio.wait_for(
            get_provider(secondary=True).generate_json(system, user),
            timeout=settings.fact_verifier_timeout_seconds,
        )
        classified = raw.get("results", []) if isinstance(raw, dict) else []
    except Exception as exc:
        logger.warning("[fact-search] verifier degraded: %s", exc)
        classified = []

    by_id = {x.get("id"): x for x in classified if isinstance(x, dict) and isinstance(x.get("id"), int)}
    for i, item in enumerate(with_sources):
        c = by_id.get(i, {})
        status = str(c.get("status", "questionable")).strip().lower()
        source_level = str(c.get("source_level", "secondary")).strip().lower()
        if status not in VALID_STATUSES:
            status = "questionable"
        if source_level not in VALID_SOURCE_LEVELS:
            source_level = "secondary"
        source_indices = c.get("source_indices", [])
        selected = []
        if isinstance(source_indices, list):
            for j in source_indices[:3]:
                if isinstance(j, int) and 0 <= j < len(item["sources"]):
                    selected.append(item["sources"][j])
        if not selected:
            selected = item["sources"][:2]
        results.append({
            "claim": item["claim"],
            "type": item["type"],
            "status": status,
            "source_level": source_level,
            "evidence": str(c.get("evidence", "搜索到相关来源，但自动核验未形成稳定结论。"))[:1200],
            "notes": str(c.get("notes", ""))[:800],
            "sources": [
                {"title": s.get("title", ""), "url": s.get("url", ""), "snippet": s.get("snippet", "")[:600]}
                for s in selected
            ],
        })
    return results


async def verify_article_facts(article: str, content_type: str) -> FactSearchOutcome:
    if settings.fact_search_provider.lower().strip() != "tavily":
        return FactSearchOutcome("NOT_RUN", [], f"事实搜索未执行：不支持的 FACT_SEARCH_PROVIDER={settings.fact_search_provider}。")
    if not _search_key():
        return FactSearchOutcome("NOT_RUN", [], "事实搜索未执行：Render 后端尚未配置 FACT_SEARCH_API_KEY。")

    started = time.perf_counter()
    logger.info("[fact-search] extract_claims start max=%d", settings.fact_search_max_claims)
    try:
        claims = await _extract_claims(article, content_type)
    except Exception as exc:
        logger.warning("[fact-search] claim extraction failed: %s", exc)
        return FactSearchOutcome("NOT_RUN", [], "事实搜索未完成：关键事实识别失败，本次审核仍按未联网核验处理。")
    logger.info("[fact-search] extract_claims done claims=%d elapsed=%.2fs", len(claims), time.perf_counter() - started)
    if not claims:
        return FactSearchOutcome("PARTIAL", [], "已执行事实扫描，但未识别到需要优先联网核验的关键客观事实。", 0)

    t = time.perf_counter()
    enriched = await _search_claims(claims)
    logger.info("[fact-search] web_search done claims=%d elapsed=%.2fs", len(enriched), time.perf_counter() - t)
    t = time.perf_counter()
    results = await _classify(enriched)
    logger.info("[fact-search] classify done results=%d elapsed=%.2fs total=%.2fs", len(results), time.perf_counter() - t, time.perf_counter() - started)
    return FactSearchOutcome(
        "PARTIAL",
        results,
        f"已联网核验 {len(results)} 条优先级较高的客观事实；仅覆盖列出的事实，未覆盖内容不得自动判错。",
        len(results),
    )
