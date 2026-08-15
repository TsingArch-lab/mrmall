from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.review_core import applicable_rule_ids
from app.execution_plan import build_execution_plan, build_rule_test_batches

for ctype in 'ABCDE':
    applicable=applicable_rule_ids(ctype)
    plan=build_execution_plan(applicable)
    batches=build_rule_test_batches(plan.map_aware_rule_ids)
    flat=[rid for b in batches for rid in b.rule_ids]
    assert set(flat) == set(plan.map_aware_rule_ids), (ctype, flat, plan.map_aware_rule_ids)
    assert len(flat)==len(set(flat))
    assert set(plan.direct_rule_ids).isdisjoint(flat)
    assert set(plan.direct_rule_ids)|set(flat)==set(applicable)
    assert 1 <= len(batches) <= 3
print('[PASS] Rule Test Batch exact partition for A/B/C/D/E')
