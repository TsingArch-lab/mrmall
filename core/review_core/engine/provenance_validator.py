#!/usr/bin/env python3
"""Deterministic provenance validator for author-facing negative feedback.
It validates provenance only; it does not judge writing quality.
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(registry, evaluation, feedback):
    rules={r["rule_id"]:r for r in registry["rules"]}
    failed={r["rule_id"] for r in evaluation.get("failed_rules",[])}
    errors=[]

    def check_candidate(label,c):
        if c is None: return
        ids=c.get("supporting_rule_ids",[])
        if not ids:
            errors.append(f"{label}: missing supporting_rule_ids")
            return
        for rid in ids:
            if rid not in rules:
                errors.append(f"{label}: unknown Rule ID {rid}")
            elif rid not in failed:
                errors.append(f"{label}: Rule {rid} is not FAIL in current evaluation")
        if not c.get("article_evidence"):
            errors.append(f"{label}: missing article_evidence")

    check_candidate("core_diagnosis", feedback.get("core_diagnosis"))
    for i,c in enumerate(feedback.get("issue_candidates",[]),1):
        check_candidate(f"issue_{i}",c)

    # hard consistency: no negative author judgement when no FAIL exists
    if not failed and (feedback.get("core_diagnosis") or feedback.get("issue_candidates")):
        errors.append("negative feedback exists while failed Rule set is empty")

    return errors


def main():
    if len(sys.argv)!=4:
        print("usage: provenance_validator.py REGISTRY.json EVALUATION.json FEEDBACK.json")
        return 2
    errors=validate(load(sys.argv[1]),load(sys.argv[2]),load(sys.argv[3]))
    if errors:
        print(json.dumps({"valid":False,"errors":errors},ensure_ascii=False,indent=2))
        return 1
    print(json.dumps({"valid":True,"errors":[]},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
