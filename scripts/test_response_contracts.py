from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.llm import _extract_json
from app.contracts import normalize_router, normalize_rule_evaluation, ContractError


def assert_eq(a,b,msg=""):
    if a != b:
        raise AssertionError(f"{msg}: {a!r} != {b!r}")


def test_extract_json():
    assert_eq(_extract_json('{"a":1}'), {"a":1})
    assert_eq(_extract_json('```json\n{"a":1}\n```'), {"a":1})
    assert_eq(_extract_json('说明文字\n{"a":{"x":"}"}, "b":2}\n尾巴'), {"a":{"x":"}"},"b":2})


def test_router_variants():
    assert_eq(normalize_router({"content_type":"D"})["content_type"], "D")
    assert_eq(normalize_router({"type":"D类"})["content_type"], "D")
    assert_eq(normalize_router({"result":{"category":"类型B"}})["content_type"], "B")
    assert_eq(normalize_router({"label":"内省/态度声明稿"})["content_type"], "D")


def test_evaluator_variants():
    supplied=["G001","I005"]
    data={
        "content_type":"D",
        "passed_rule_ids":["G001"],
        "failed_rules":[{
            "rule_id":"I005",
            "evidence":"原文证据",
            "reason":"判断强于证据"
        }],
        "na_rule_ids":[],
        "unresolved_rules":[]
    }
    out=normalize_rule_evaluation(data,content_type="D",supplied_rule_ids=supplied)
    assert_eq(out["evaluated_rule_ids"], supplied)
    assert_eq(out["failed_rules"][0]["article_evidence"], ["原文证据"])

    bad={
        "content_type":"D",
        "passed_rule_ids":["G001"],
        "failed_rules":[],
        "na_rule_ids":[],
        "unresolved_rules":[]
    }
    try:
        normalize_rule_evaluation(bad,content_type="D",supplied_rule_ids=supplied)
    except ContractError:
        pass
    else:
        raise AssertionError("missing Rule IDs must fail contract")


if __name__=="__main__":
    test_extract_json()
    test_router_variants()
    test_evaluator_variants()
    print("[PASS] response contract tests")
