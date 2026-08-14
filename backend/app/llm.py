from __future__ import annotations
import json, re
from typing import Any
import httpx
from .config import settings

class LLMError(RuntimeError):
    pass

def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise

class Provider:
    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError

class OpenAICompatibleProvider(Provider):
    """Providers exposing an OpenAI-compatible /chat/completions endpoint."""
    async def _request(self, system: str, user: str, use_json_mode: bool=True) -> str:
        if not settings.llm_api_key: raise LLMError("LLM_API_KEY is missing")
        if not settings.llm_model: raise LLMError("LLM_MODEL is missing")
        url=f"{settings.llm_base_url}/chat/completions"
        headers={"Authorization":f"Bearer {settings.llm_api_key}","Content-Type":"application/json"}
        payload={"model":settings.llm_model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"temperature":0}
        if use_json_mode: payload["response_format"]={"type":"json_object"}
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp=await client.post(url,headers=headers,json=payload)
            if resp.status_code>=400 and use_json_mode:
                payload.pop("response_format",None)
                resp=await client.post(url,headers=headers,json=payload)
            if resp.status_code>=400:
                raise LLMError(f"Provider error {resp.status_code}: {resp.text[:800]}")
            data=resp.json()
        try: return data["choices"][0]["message"]["content"]
        except Exception as exc: raise LLMError(f"Unexpected provider response: {str(data)[:800]}") from exc

    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        text=await self._request(system,user,True)
        try: return _extract_json(text)
        except Exception:
            # One bounded repair attempt. The repair call may fix syntax only, not re-review content.
            repair_system="你只修复 JSON 格式，不得新增、删除或改变任何实质判断。只输出合法 JSON。"
            repair_user="请把下面内容修复为合法 JSON：\\n\\n"+text
            repaired=await self._request(repair_system,repair_user,True)
            try: return _extract_json(repaired)
            except Exception as exc: raise LLMError("Model returned invalid JSON after one repair attempt") from exc

class MockProvider(Provider):
    async def generate_json(self, system: str, user: str) -> dict[str, Any]:
        if "CONTENT_TYPE_ROUTER" in system or "CONTENT_TYPE_ROUTER" in user:
            return {"content_type":"D","confidence":0.5,"primary_value":"MOCK：仅用于检查网站流程"}
        if "FEEDBACK_COMPOSER" in system or "FEEDBACK_COMPOSER" in user:
            m=re.search(r"FINAL_JUDGEMENT:\s*(.+)",user)
            final=m.group(1).strip() if m else "可以继续"
            return {"final_judgement":final,"dimension_assessments":{},"core_diagnosis":None,"issue_candidates":[],"strengths":["MOCK 模式：网站链路已跑通；此结果不是实际审稿结论。"]}
        ids=re.findall(r'"rule_id"\s*:\s*"([A-Z0-9_]+)"',user)
        m=re.search(r"CONTENT_TYPE:\s*([A-E])",user); ctype=m.group(1) if m else "D"
        return {"content_type":ctype,"evaluated_rule_ids":ids,"passed_rule_ids":ids,"failed_rules":[],"na_rule_ids":[],"unresolved_rules":[]}

def get_provider() -> Provider:
    p=settings.llm_provider.lower()
    if p=="mock": return MockProvider()
    if p in {"openai_compatible","openai-compatible","openai"}: return OpenAICompatibleProvider()
    raise LLMError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
