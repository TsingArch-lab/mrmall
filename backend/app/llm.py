from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("mall_content_os.llm")


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    """Extract one JSON object from a model response.

    Supports:
    - pure JSON
    - ```json fenced JSON
    - explanatory text surrounding one JSON object
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty model response")

    # Correctly remove Markdown code fences. v0.1.1 accidentally matched literal "\\s".
    text = re.sub(r"^\s*```(?:json|JSON)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("model JSON root must be an object")
        return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Find a balanced JSON object rather than blindly slicing first { to last }.
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model response")

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                data = json.loads(text[start:i+1])
                if not isinstance(data, dict):
                    raise ValueError("model JSON root must be an object")
                return data
    raise ValueError("unterminated JSON object in model response")


def _normalize_message_content(message: dict[str, Any]) -> str:
    """Normalize OpenAI-compatible message content across providers."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif item.get("type") == "text" and isinstance(item.get("content"), str):
                    parts.append(item["content"])
        if parts:
            return "\n".join(parts)
    # Some reasoning-compatible providers may place a final answer elsewhere.
    for key in ("final", "output_text", "reasoning_content"):
        if isinstance(message.get(key), str) and message[key].strip():
            return message[key]
    raise LLMError("Provider returned no textual message content")


def _safe_debug_response(text: str) -> None:
    if not settings.llm_debug_raw_response:
        return
    compact = text.replace("\n", "\\n")
    logger.warning("LLM raw response (truncated): %s", compact[:settings.llm_debug_max_chars])


class Provider:
    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError


class OpenAICompatibleProvider(Provider):
    """Provider exposing an OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, model_override: str | None = None, timeout_override: float | None = None):
        self.model = (model_override or settings.llm_model).strip()
        self.timeout_seconds = timeout_override or settings.llm_timeout_seconds

    async def _request(self, system: str, user: str, use_json_mode: bool = True) -> str:
        if not settings.llm_api_key:
            raise LLMError("LLM_API_KEY is missing")
        if not self.model:
            raise LLMError("LLM_MODEL is missing")

        url = f"{settings.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(settings.llm_http_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                # A provider may support OpenAI Chat Completions but not response_format.
                if resp.status_code >= 400 and use_json_mode and resp.status_code in {400, 404, 422}:
                    payload.pop("response_format", None)
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code in {408, 429, 500, 502, 503, 504} and attempt < settings.llm_http_retries:
                    await asyncio.sleep(0.6 * (2 ** attempt))
                    continue

                if resp.status_code >= 400:
                    raise LLMError(f"Provider error {resp.status_code}: {resp.text[:800]}")

                data = resp.json()
                try:
                    message = data["choices"][0]["message"]
                except Exception as exc:
                    raise LLMError(f"Unexpected provider response envelope: {str(data)[:800]}") from exc

                text = _normalize_message_content(message)
                _safe_debug_response(text)
                return text

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < settings.llm_http_retries:
                    await asyncio.sleep(0.6 * (2 ** attempt))
                    continue
                raise LLMError(f"Provider network/timeout error after retries: {exc}") from exc

        raise LLMError(f"Provider request failed: {last_error}")

    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        text = await self._request(system, user, True)
        try:
            return _extract_json(text)
        except Exception:
            # One bounded syntax-only repair attempt.
            repair_system = (
                "你是 JSON_SYNTAX_REPAIR。你只能修复 JSON 语法与代码围栏，"
                "不得新增、删除、重新判断或改变任何实质内容。只输出一个合法 JSON 对象。"
            )
            repair_user = "把以下模型原始输出仅修复为合法 JSON 对象：\n\n" + text
            repaired = await self._request(repair_system, repair_user, True)
            try:
                return _extract_json(repaired)
            except Exception as exc:
                raise LLMError("Model returned invalid JSON after one syntax repair attempt") from exc


class MockProvider(Provider):
    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        if "ARTICLE_MAP_BUILDER" in system or "ARTICLE_MAP_BUILDER" in user:
            article_match = re.search(r"ARTICLE:\n(.+)", user, re.S)
            article = article_match.group(1).strip() if article_match else ""
            quote = article[:80].strip()
            return {
                "core_question": "MOCK：文章主要任务",
                "thesis": "MOCK：文章核心判断",
                "units": [{
                    "unit_id": "U01",
                    "heading": "MOCK",
                    "anchor_quote": quote,
                    "role": "opening",
                    "main_claim": "MOCK：首个论证单元",
                    "evidence_used": [],
                    "mechanism": "",
                    "relation_to_prior": "opens",
                    "new_contribution": "提出文章任务",
                }] if quote else [],
                "fact_claims": [],
            }
        if "CONTENT_TYPE_ROUTER" in system or "CONTENT_TYPE_ROUTER" in user:
            return {
                "content_type": "D",
                "confidence": 0.5,
                "primary_value": "MOCK：仅用于检查网站流程",
            }
        if "FEEDBACK_COMPOSER" in system or "FEEDBACK_COMPOSER" in user:
            m = re.search(r"FINAL_JUDGEMENT:\s*(.+)", user)
            final = m.group(1).strip() if m else "可以继续"
            return {
                "final_judgement": final,
                "dimension_assessments": {},
                "core_diagnosis": None,
                "issue_candidates": [],
                "strengths": ["MOCK 模式：网站链路已跑通；此结果不是实际审稿结论。"],
            }
        ids = re.findall(r'"rule_id"\s*:\s*"([A-Z0-9_]+)"', user)
        m = re.search(r"CONTENT_TYPE:\s*([A-E])", user)
        ctype = m.group(1) if m else "D"
        return {
            "content_type": ctype,
            "evaluated_rule_ids": ids,
            "passed_rule_ids": ids,
            "failed_rules": [],
            "na_rule_ids": [],
            "unresolved_rules": [],
        }


def get_provider(*, secondary: bool = False) -> Provider:
    p = settings.llm_provider.lower().strip()
    if p == "mock":
        return MockProvider()
    if p in {"openai_compatible", "openai-compatible", "openai"}:
        if secondary:
            model = settings.llm_model_secondary.strip() or settings.llm_model
            return OpenAICompatibleProvider(model_override=model, timeout_override=settings.llm_secondary_timeout_seconds)
        return OpenAICompatibleProvider()
    raise LLMError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
