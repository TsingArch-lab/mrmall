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
VALID_RISK_TAGS = {"anchor", "named_story", "quote", "authority_attribution", "operating_metric", "extreme_claim", "other"}
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
1. 只提取客观可核验事实，不得为作者自己的分析、因果判断、价值判断、趋势推论寻找支持材料。
2. 最多返回 MAX_CLAIMS 条；不要为了凑数搜索低价值事实。
3. 如果原文明示某项经营数据来自项目方内部提供、内部口径、采访现场口径，且没有公开来源线索，不要返回该项，不浪费搜索。

优先级标准（非常重要）：
A. 高优先级【基础锚点事实 anchor】
- 项目面积、开业年份、所在城市/区位、项目前身、关键历史节点、企业/项目主体关系等。
- 这类事实通常低争议，但一旦错误会污染全文基础，因此必须优先核验。

B. 高优先级【有名有姓的故事 named_story】
- 明确到人物、企业、项目、会议、事件的具体故事：谁在什么时候做了什么、为什么做出某个决定、发生过什么具体情节。
- 重点防止二手传播把故事加工、拼接或张冠李戴。

C. 高优先级【名人名言 quote】
- 明确声称某位人物、企业高管、专家说过某句话或表达过某个观点。
- 优先核验是否真的说过、原意是否一致、时间和场合是否准确。

D. 最高风险【诉诸权威 authority_attribution】
- “某报告显示”“某研究发现”“某专家指出”“某书中提出”“某机构统计”“某论文证明”等借助外部权威提高可信度的表述。
- 这是虚构来源、误引数据、张冠李戴、把评论写成研究结论的高发区，必须优先进入前 MAX_CLAIMS。
- search_query 必须尽量包含报告/研究/书名/机构/专家/原始数字或关键词，以便找到原始来源。

E. 一般经营数据【operating_metric】不天然高优先级
- 销售额、客流、坪效、增长率、转化率等，不因为“有数字”就自动占用名额。
- 只有当它承担核心论证支点、存在公开来源线索，或与其他来源发生明显冲突时，才优先搜索。

F. 营销型极值【extreme_claim】不自动高优先级
- “全国第一 / 区域首店 / 唯一一家 / 最大 / 首个”等，不因为极值词本身就必须查。
- 只有当该极值对核心论证重要时才进入前 MAX_CLAIMS。

排序原则：
- authority_attribution 优先；
- anchor / named_story / quote 紧随其后；
- operating_metric / extreme_claim 仅在对核心论证重要时进入；
- 同一事实链只选最关键的支点，避免把一句话中的多个相近数字拆成多次搜索。

search_query 要适合直接送入中文互联网搜索，保留关键专名、数字、年份、报告名、书名或人物名。

只输出 JSON：
{"claims":[{"claim":"原文中的完整事实声明","type":"data|case|quote","risk_tag":"anchor|named_story|quote|authority_attribution|operating_metric|extreme_claim|other","importance":"high|medium","search_query":"搜索词"}]}。"""
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
        risk_tag = str(item.get("risk_tag", "other")).strip().lower()
        importance = str(item.get("importance", "medium")).strip().lower()
        if not claim or not query or claim in seen:
            continue
        if ctype not in VALID_TYPES:
            ctype = "case"
        if risk_tag not in VALID_RISK_TAGS:
            risk_tag = "other"
        # User calibration: anchors, named stories, quotes and authority attributions
        # are inherently high-priority verification targets.
        if risk_tag in {"anchor", "named_story", "quote", "authority_attribution"}:
            importance = "high"
        elif importance not in {"high", "medium"}:
            importance = "medium"
        seen.add(claim)
        out.append({"claim": claim, "type": ctype, "risk_tag": risk_tag, "importance": importance, "search_query": query})

    priority = {
        "authority_attribution": 0,
        "anchor": 1,
        "named_story": 2,
        "quote": 3,
        "operating_metric": 4,
        "extreme_claim": 5,
        "other": 6,
    }
    out.sort(key=lambda x: (priority.get(x["risk_tag"], 9), 0 if x["importance"] == "high" else 1))
    return out[: settings.fact_search_max_claims]


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
            "importance": item.get("importance", "medium"),
            "risk_tag": item.get("risk_tag", "other"),
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
            "risk_tag": item.get("risk_tag", "other"),
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

对 risk_tag=authority_attribution 的内容执行更严格的“权威归属核验”：
1. 优先确认被引用的报告/研究/书/专家/机构本身是否真实存在；
2. 再确认原始来源是否真的包含文章声称的数据或结论；
3. 检查是否出现数字口径改变、删掉限定条件、把媒体转述当原始研究、把个人评论写成机构结论、张冠李戴；
4. 只有二手网页重复同一句话、却找不到其所称原始权威来源时，不得判 confirmed，应判 questionable 或 no_reliable_source；
5. 如果原始权威来源明确与文章相反，判 contradicted，并在 evidence 中明确写出“权威来源引用错误”的具体差异。

对 quote：核验人物是否真的说过、原意、时间和场合；只有二手转述而无可靠出处时保持谨慎。
对 anchor：优先核对面积、开业年份、主体关系、前身等基础锚点是否一致。

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
            "importance": item.get("importance", "medium"),
            "risk_tag": item.get("risk_tag", "other"),
            "authority_warning": bool(item.get("risk_tag") == "authority_attribution" and status in {"questionable", "contradicted"}),
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
