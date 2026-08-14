from __future__ import annotations
from typing import Any
CLUSTER_HINTS={
    "evidence_boundary":{"rule_ids":{"E003","I005","I006","S004","F003"},"label":"证据边界与外推强度"},
    "pr_self_proof":{"rule_ids":{"E002","G002","I005","X002"},"label":"项目方自证与判断强度"},
    "mechanism_empty":{"rule_ids":{"I001","I004","X002","X003"},"label":"机制不足与抽象判断"},
}
NON_AUTHOR_STANDALONE_RULES={"F001","F002"}

def cluster_failed_rules(failed_rules:list[dict[str,Any]], registry:dict[str,dict[str,Any]])->list[dict[str,Any]]:
    groups=[]; assigned=set()
    for key,cfg in CLUSTER_HINTS.items():
        members=[]
        for idx,fail in enumerate(failed_rules):
            rid=fail["rule_id"]
            if idx in assigned or rid in NON_AUTHOR_STANDALONE_RULES: continue
            if rid in cfg["rule_ids"]: members.append((idx,fail))
        if len(members)>=2:
            assigned.update(idx for idx,_ in members)
            ids=[f["rule_id"] for _,f in members]
            evidence=[]
            for _,f in members:
                for e in f.get("article_evidence",[]):
                    if e not in evidence: evidence.append(e)
            groups.append({"cluster_id":key,"cluster_hint":cfg["label"],"supporting_rule_ids":ids,"article_evidence":evidence,"rule_fail_conditions":{rid:registry[rid].get("fail_condition","") for rid in ids},"rule_match_explanations":{f["rule_id"]:f.get("match_explanation","") for _,f in members}})
    for idx,fail in enumerate(failed_rules):
        if idx in assigned: continue
        rid=fail["rule_id"]
        if rid in NON_AUTHOR_STANDALONE_RULES: continue
        groups.append({"cluster_id":f"single:{rid}","cluster_hint":registry[rid].get("name",rid),"supporting_rule_ids":[rid],"article_evidence":list(fail.get("article_evidence",[])),"rule_fail_conditions":{rid:registry[rid].get("fail_condition","")},"rule_match_explanations":{rid:fail.get("match_explanation","")}})
    return groups
