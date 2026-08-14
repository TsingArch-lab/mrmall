from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from .config import settings
from .llm import LLMError
from .models import ReviewRequest, ReviewResponse
from .review_core import registry_hash, review_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mall_content_os.api")

app = FastAPI(title="Mall Content OS Review API", version="0.1.2")

origins = (
    ["*"]
    if settings.cors_origins.strip() == "*"
    else [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_token(authorization: str | None):
    if not settings.app_access_token:
        return
    expected = f"Bearer {settings.app_access_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "mall-content-os-review",
        "version": "0.1.2",
        "registry_hash": registry_hash(),
        "provider": settings.llm_provider,
        "model": settings.llm_model or "mock",
    }


@app.post("/api/review", response_model=ReviewResponse)
async def review(
    req: ReviewRequest,
    authorization: str | None = Header(default=None),
):
    check_token(authorization)
    try:
        return await review_article(req.article, req.content_type, req.verify_facts)
    except LLMError as exc:
        # Controlled model/provider/contract failure: safe to show concise message to operator.
        logger.warning("Review LLM failure: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Review validation failure: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected review failure")
        raise HTTPException(
            status_code=500,
            detail="审核服务发生未预期错误。请查看 Render Logs 中对应请求的错误信息。",
        ) from exc
