from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
CORE_DIR = PROJECT_DIR / "core" / "review_core"


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    llm_model: str = os.getenv("LLM_MODEL", "")
    # Optional faster model for non-gating author-facing post-processing.
    # If omitted, secondary stages reuse LLM_MODEL.
    llm_model_secondary: str = os.getenv("LLM_MODEL_SECONDARY", "")
    llm_secondary_timeout_seconds: float = float(os.getenv("LLM_SECONDARY_TIMEOUT_SECONDS", "90"))
    llm_evaluator_stage_timeout_seconds: float = float(os.getenv("LLM_EVALUATOR_STAGE_TIMEOUT_SECONDS", "240"))
    llm_router_stage_timeout_seconds: float = float(os.getenv("LLM_ROUTER_STAGE_TIMEOUT_SECONDS", "90"))
    llm_adjudicator_stage_timeout_seconds: float = float(os.getenv("LLM_ADJUDICATOR_STAGE_TIMEOUT_SECONDS", "90"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
    llm_http_retries: int = int(os.getenv("LLM_HTTP_RETRIES", "2"))
    llm_debug_raw_response: bool = _bool_env("LLM_DEBUG_RAW_RESPONSE", False)
    llm_debug_max_chars: int = int(os.getenv("LLM_DEBUG_MAX_CHARS", "1200"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    app_access_token: str = os.getenv("APP_ACCESS_TOKEN", "")
    max_article_chars: int = int(os.getenv("MAX_ARTICLE_CHARS", "50000"))


settings = Settings()
