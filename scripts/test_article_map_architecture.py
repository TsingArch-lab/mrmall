#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.article_map import normalize_article_map
from app.execution_plan import MAP_AWARE_RULE_IDS, build_execution_plan
from app.fact_search import normalize_claim_items
from app.review_core import applicable_rule_ids

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # 1) Every runtime applicable Rule must be executed exactly once.
    for ctype in "ABCDE":
        applicable = applicable_rule_ids(ctype)
        plan = build_execution_plan(applicable)
        assert len(plan.all_rule_ids) == len(set(plan.all_rule_ids))
        assert set(plan.all_rule_ids) == set(applicable)
        assert not (set(plan.direct_rule_ids) & set(plan.map_aware_rule_ids))

    # 2) The benchmark Rules whose execution needs cross-unit comparison are map-aware.
    for rid in ["S007", "S001", "I005", "I004", "T001", "T002", "F003"]:
        assert rid in MAP_AWARE_RULE_IDS, rid
    # Typical local/opening/expression rules remain on direct path.
    plan_a = build_execution_plan(applicable_rule_ids("A"))
    for rid in ["G001", "S002", "S003", "X001", "X004"]:
        assert rid in plan_a.direct_rule_ids, rid

    # 3) Article Map normalization is descriptive and exact-quote safe.
    article = "第一段提出问题。第二段解释机制。第三段总结。"
    raw = {
        "core_question": "文章在解释什么？",
        "thesis": "解释一个机制",
        "units": [
            {"unit_id":"x","heading":"开头","anchor_quote":"第一段提出问题。","role":"opening","main_claim":"提出问题","evidence_used":[],"mechanism":"","relation_to_prior":"opens","new_contribution":"提出问题"},
            {"unit_id":"y","heading":"机制","anchor_quote":"不存在的原句","role":"mechanism","main_claim":"解释机制","evidence_used":[],"mechanism":"X影响Y","relation_to_prior":"adds_mechanism","new_contribution":"增加机制"},
        ],
    }
    m = normalize_article_map(raw, article)
    assert m["state"] == "READY"
    assert m["units"][0]["anchor_quote"] == "第一段提出问题。"
    assert m["units"][1]["anchor_quote"] == ""  # hallucinated evidence cannot propagate
    assert "quality" not in json.dumps(m, ensure_ascii=False).lower()

    # 4) Fact-claim priority is unchanged and Article Map can feed the same normalizer.
    claims = normalize_claim_items([
        {"claim":"销售增长20%","type":"data","risk_tag":"operating_metric","importance":"high","search_query":"销售 增长20%"},
        {"claim":"某报告显示X","type":"case","risk_tag":"authority_attribution","importance":"medium","search_query":"某报告 X"},
        {"claim":"项目2024年开业","type":"data","risk_tag":"anchor","importance":"medium","search_query":"项目 2024 开业"},
    ])
    assert [x["risk_tag"] for x in claims[:3]] == ["authority_attribution", "anchor", "operating_metric"]
    assert claims[0]["importance"] == "high"

    # 5) Gate registry is byte-identical to the locked v0.1.7.2 Gate hash.
    gate = ROOT / "core" / "review_core" / "portable" / "runtime" / "gate_registry.json"
    assert sha(gate) == "6dec70cdd4ad7225e63764f164a2ee9c92d96de13fec9e92a856f1f9c5b1ca0f"

    print("[PASS] Article Map architecture: exact coverage, map safety, fact reuse, Gate unchanged")


if __name__ == "__main__":
    main()
