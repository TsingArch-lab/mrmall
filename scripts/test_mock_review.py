from __future__ import annotations
import asyncio, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

os.environ["LLM_PROVIDER"]="mock"

from app.review_core import review_article

async def main():
    article=("这是一篇测试文章。商业地产进入新的经营周期，作者试图从行业压力中讨论个人应对。"
             "这段文字用于测试自动分类、Rules 执行、Gate 聚合和反馈输出。" * 5)
    result=await review_article(article,"AUTO",False)
    assert result["content_type"] in {"A","B","C","D","E"}
    assert result["final_judgement"] in {"可以继续","需要修改"}
    assert "registry_hash" in result
    print("[PASS] mock review integration")

if __name__=="__main__":
    asyncio.run(main())
