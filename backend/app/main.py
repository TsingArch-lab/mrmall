from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from .config import settings
from .llm import LLMError
from .models import ReviewRequest, ReviewResponse
from .fact_search import fact_search_available
from .review_core import registry_hash, review_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mall_content_os.api")

app = FastAPI(title="Mall Content OS Review API", version="0.1.7.0")

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

# In-memory job state intentionally contains only active/recent review results.
# It avoids keeping one browser->Render HTTP request open for several minutes.
JOBS: dict[str, dict[str, Any]] = {}
MAX_JOBS = 100


def check_token(authorization: str | None):
    if not settings.app_access_token:
        return
    expected = f"Bearer {settings.app_access_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _trim_jobs() -> None:
    if len(JOBS) <= MAX_JOBS:
        return
    done = sorted(
        ((jid, item) for jid, item in JOBS.items() if item.get("status") in {"completed", "failed"}),
        key=lambda x: x[1].get("updated_at", 0),
    )
    for jid, _ in done[: max(0, len(JOBS) - MAX_JOBS)]:
        JOBS.pop(jid, None)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "mall-content-os-review",
        "version": "0.1.7.0",
        "registry_hash": registry_hash(),
        "provider": settings.llm_provider,
        "model": settings.llm_model or "mock",
        "secondary_model": settings.llm_model_secondary or settings.llm_model or "mock",
        "fact_search_provider": settings.fact_search_provider,
        "fact_search_available": fact_search_available(),
    }


@app.post("/api/review", response_model=ReviewResponse)
async def review(
    req: ReviewRequest,
    authorization: str | None = Header(default=None),
):
    """Compatibility endpoint. New frontend uses job+polling endpoints below."""
    check_token(authorization)
    request_started = time.perf_counter()
    logger.info("[api] /api/review start content_type=%s article_chars=%d", req.content_type, len(req.article))
    try:
        result = await review_article(req.article, req.content_type, req.verify_facts)
        logger.info("[api] /api/review done elapsed=%.2fs final=%s", time.perf_counter() - request_started, result.get("final_judgement"))
        return result
    except LLMError as exc:
        logger.warning("Review LLM failure: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Review validation failure: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected review failure")
        raise HTTPException(status_code=500, detail="审核服务发生未预期错误。请查看 Render Logs 中对应请求的错误信息。") from exc


async def _run_review_job(job_id: str, req: ReviewRequest) -> None:
    started = time.perf_counter()

    def progress(stage: str, message: str) -> None:
        item = JOBS.get(job_id)
        if not item:
            return
        item.update({
            "stage": stage,
            "message": message,
            "updated_at": time.time(),
            "elapsed_seconds": round(time.perf_counter() - started, 1),
        })

    try:
        result = await review_article(
            req.article,
            req.content_type,
            req.verify_facts,
            progress_callback=progress,
        )
        JOBS[job_id].update({
            "status": "completed",
            "stage": "COMPLETED",
            "message": "审核完成",
            "result": result,
            "updated_at": time.time(),
            "elapsed_seconds": round(time.perf_counter() - started, 1),
        })
        logger.info("[job] completed id=%s elapsed=%.2fs final=%s", job_id, time.perf_counter() - started, result.get("final_judgement"))
    except LLMError as exc:
        logger.warning("[job] LLM failure id=%s: %s", job_id, exc)
        JOBS[job_id].update({"status": "failed", "stage": "FAILED", "message": str(exc), "updated_at": time.time(), "elapsed_seconds": round(time.perf_counter() - started, 1)})
    except ValueError as exc:
        logger.warning("[job] validation failure id=%s: %s", job_id, exc)
        JOBS[job_id].update({"status": "failed", "stage": "FAILED", "message": str(exc), "updated_at": time.time(), "elapsed_seconds": round(time.perf_counter() - started, 1)})
    except Exception:
        logger.exception("[job] unexpected failure id=%s", job_id)
        JOBS[job_id].update({"status": "failed", "stage": "FAILED", "message": "审核服务发生未预期错误，请查看 Render Logs。", "updated_at": time.time(), "elapsed_seconds": round(time.perf_counter() - started, 1)})
    finally:
        _trim_jobs()


@app.post("/api/review/jobs")
async def create_review_job(
    req: ReviewRequest,
    authorization: str | None = Header(default=None),
):
    check_token(authorization)
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "stage": "QUEUED",
        "message": "审核任务已创建",
        "created_at": time.time(),
        "updated_at": time.time(),
        "elapsed_seconds": 0,
        "result": None,
    }
    asyncio.create_task(_run_review_job(job_id, req))
    logger.info("[job] created id=%s content_type=%s article_chars=%d", job_id, req.content_type, len(req.article))
    return {"job_id": job_id, "status": "running", "stage": "QUEUED", "message": "审核任务已创建"}


@app.get("/api/review/jobs/{job_id}")
async def get_review_job(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    check_token(authorization)
    item = JOBS.get(job_id)
    if not item:
        raise HTTPException(status_code=404, detail="审核任务不存在或服务已重启，请重新提交。")
    return item
