#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json

import app.review_core as rc
from app.verification import make_verification_context


ARTICLE = "前文已经说清内容先行。行业痛点总结再次说内容先行。结尾又说长期主义和内容驱动。"
MAP = {
    "state": "READY",
    "core_question": "为什么学习某项目容易只学外形",
    "thesis": "核心在内容与组织机制",
    "units": [
        {"unit_id":"U01","heading":"机制","anchor_quote":"前文已经说清内容先行。","role":"mechanism","main_claim":"内容先行","evidence_used":[],"mechanism":"内容先于招商","relation_to_prior":"opens","new_contribution":"提出内容先行"},
        {"unit_id":"U02","heading":"总结","anchor_quote":"行业痛点总结再次说内容先行。","role":"summary","main_claim":"内容先行","evidence_used":[],"mechanism":"","relation_to_prior":"restates","new_contribution":"回扣内容先行"},
        {"unit_id":"U03","heading":"结尾","anchor_quote":"结尾又说长期主义和内容驱动。","role":"conclusion","main_claim":"长期主义和内容驱动","evidence_used":[],"mechanism":"","relation_to_prior":"restates","new_contribution":"再次总结"}
    ]
}


class ProbeProvider:
    async def generate_json(self, system: str, user: str):
        assert "MAP_AWARE" in user
        assert '"relation_to_prior": "restates"' in user
        ids = []
        for rid in ["S007"]:
            if f'"rule_id": "{rid}"' in user:
                ids.append(rid)
        return {
            "content_type": "B",
            "evaluated_rule_ids": ids,
            "passed_rule_ids": [],
            "failed_rules": [{
                "rule_id": "S007",
                "article_evidence": ["行业痛点总结再次说内容先行。", "结尾又说长期主义和内容驱动。"],
                "match_explanation": "这些单元在前文已建立同一命题后主要承担重述；按S007既有删除测试/边际价值测试，未增加新的机制、条件或差异。"
            }],
            "na_rule_ids": [],
            "unresolved_rules": []
        }


async def main():
    original = rc.get_provider
    rc.get_provider = lambda *args, **kwargs: ProbeProvider()
    try:
        result = await rc.evaluate_rule_ids(
            ARTICLE, "B", make_verification_context(False, [], state="NOT_RUN"), ["S007"],
            article_map=MAP, evaluation_mode="MAP_AWARE", system_role="MAP_AWARE_RULE_EXECUTOR"
        )
        assert result["failed_rules"][0]["rule_id"] == "S007"
        assert result["failed_rules"][0]["article_evidence"][0] in ARTICLE
        print("[PASS] MAP_AWARE plumbing: Article Map reaches existing Rule executor; FAIL remains S007-provenance-only")
    finally:
        rc.get_provider = original


if __name__ == "__main__":
    asyncio.run(main())
