from __future__ import annotations
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from .config import settings
from .models import ReviewRequest, ReviewResponse
from .review_core import review_article, registry_hash

app=FastAPI(title='Mall Content OS Review API',version='0.1.1')
origins=['*'] if settings.cors_origins.strip()=='*' else [x.strip() for x in settings.cors_origins.split(',') if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

def check_token(authorization: str | None):
    if not settings.app_access_token:
        return
    expected=f'Bearer {settings.app_access_token}'
    if authorization != expected:
        raise HTTPException(status_code=401,detail='Unauthorized')

@app.get('/health')
def health():
    return {'ok':True,'service':'mall-content-os-review','registry_hash':registry_hash(),'provider':settings.llm_provider}

@app.post('/api/review',response_model=ReviewResponse)
async def review(req: ReviewRequest, authorization: str | None = Header(default=None)):
    check_token(authorization)
    try:
        return await review_article(req.article,req.content_type,req.verify_facts)
    except Exception as exc:
        raise HTTPException(status_code=500,detail=str(exc)) from exc
