from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field, field_validator
from .config import settings
ContentType=Literal["AUTO","A","B","C","D","E"]
class ReviewRequest(BaseModel):
    article:str=Field(min_length=20)
    content_type:ContentType="AUTO"
    verify_facts:bool=False
    @field_validator("article")
    @classmethod
    def article_length(cls,v:str):
        if len(v)>settings.max_article_chars:
            raise ValueError(f"文章过长：当前上限 {settings.max_article_chars} 字符。")
        return v
class ReviewResponse(BaseModel):
    review_id:str; content_type:str; final_judgement:str
    dimension_states:dict[str,str]; core_diagnosis:str|None
    issues:list[dict[str,Any]]; strengths:list[Any]
    unresolved_rules:list[dict[str,Any]]; failed_rule_ids:list[str]
    model_provider:str; model:str; registry_hash:str
    verification_note:str|None=None
