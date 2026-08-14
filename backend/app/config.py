from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
BACKEND_DIR=Path(__file__).resolve().parents[1]
PROJECT_DIR=BACKEND_DIR.parent
CORE_DIR=PROJECT_DIR/"core"/"review_core"
@dataclass(frozen=True)
class Settings:
    llm_provider:str=os.getenv("LLM_PROVIDER","mock")
    llm_api_key:str=os.getenv("LLM_API_KEY","")
    llm_base_url:str=os.getenv("LLM_BASE_URL","https://api.openai.com/v1").rstrip("/")
    llm_model:str=os.getenv("LLM_MODEL","")
    llm_timeout_seconds:float=float(os.getenv("LLM_TIMEOUT_SECONDS","120"))
    cors_origins:str=os.getenv("CORS_ORIGINS","*")
    app_access_token:str=os.getenv("APP_ACCESS_TOKEN","")
    max_article_chars:int=int(os.getenv("MAX_ARTICLE_CHARS","50000"))
settings=Settings()
