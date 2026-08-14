#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT/'registry'/'compiled_rule_registry.json'
GATES = ROOT/'portable'/'runtime'/'gate_registry.json'

DIM_MAP={
 'TOPIC':'选题价值','EVIDENCE':'证据支撑','GLOBAL':'证据支撑','INSIGHT':'观点质量',
 'STRUCTURE':'结构逻辑','EXPRESSION':'表达质量','FINAL':'表达质量'
}

def load_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def rules_by_id():
    reg=load_json(REGISTRY)
    return {r['rule_id']:r for r in reg['rules']}

def applicable_rule_ids(content_type:str):
    gates=load_json(GATES)['gates']
    out=[]
    # Always global truth + router is not part of full-review evaluation if type is known.
    for gate_name in ['TOPIC','EVIDENCE','INSIGHT','STRUCTURE','FINAL']:
        g=gates[gate_name]
        out += g.get('always',[])
        out += g.get('by_type',{}).get(content_type,[])
        out += g.get('all_expression',[])
    # filter Registry applicability and dedupe
    reg=rules_by_id(); seen=set(); final=[]
    for rid in out:
        if rid in seen or rid not in reg: continue
        r=reg[rid]
        if content_type in r.get('applies_to',[]) or 'ALL' in r.get('applies_to',[]):
            seen.add(rid); final.append(rid)
    return final

def compact_rules(content_type:str):
    reg=rules_by_id()
    return [{k:reg[rid][k] for k in ['rule_id','name','stage','severity','evaluation_question','pass_condition','fail_condition','exceptions']} for rid in applicable_rule_ids(content_type)]

def aggregate(eval_result:dict):
    reg=rules_by_id(); fails=eval_result.get('failed_rules',[])
    fail_ids=[x['rule_id'] for x in fails]
    by_stage={}
    for rid in fail_ids:
        r=reg[rid]; by_stage.setdefault(r['stage'],[]).append(r)

    revise=False
    # Any BLOCKER fail in review stages revises.
    if any(reg[rid]['severity']=='BLOCKER' for rid in fail_ids): revise=True
    # Topic special A/B: two or more topic fails revises.
    if eval_result['content_type'] in {'A','B'} and len(by_stage.get('TOPIC',[]))>=2: revise=True
    # Structure/Final: >=3 major fails within the stage revises.
    for stage in ['STRUCTURE','FINAL']:
        if sum(1 for r in by_stage.get(stage,[]) if r['severity']=='MAJOR')>=3: revise=True

    final='需要修改' if revise else '可以继续'
    # STOP is intentionally not inferred from model prose in portable core.
    # It requires explicit operator/system recoverability metadata outside LLM judgement.

    dims={k:'达标' for k in ['选题价值','证据支撑','观点质量','结构逻辑','表达质量']}
    for rid in fail_ids:
        stage=reg[rid]['stage']
        dim=DIM_MAP.get(stage)
        if dim: dims[dim]='有明显问题'
    return {'final_judgement':final,'dimension_states':dims,'failed_rule_ids':fail_ids}

def validate_eval(result:dict):
    reg=rules_by_id(); supplied=set(applicable_rule_ids(result['content_type']))
    buckets=[]
    buckets += result.get('passed_rule_ids',[])
    buckets += result.get('na_rule_ids',[])
    buckets += [x['rule_id'] for x in result.get('failed_rules',[])]
    buckets += [x['rule_id'] for x in result.get('unresolved_rules',[])]
    unknown=set(buckets)-supplied
    if unknown: raise ValueError(f'Output contains unsupplied Rule IDs: {sorted(unknown)}')
    if len(buckets)!=len(set(buckets)): raise ValueError('A Rule appears in multiple status buckets.')
    return True

def main():
    if len(sys.argv)<3:
        print('Usage: reference_runtime.py compact-rules <A|B|C|D|E> | aggregate <evaluation.json>')
        return 2
    cmd=sys.argv[1]
    if cmd=='compact-rules':
        print(json.dumps(compact_rules(sys.argv[2]),ensure_ascii=False,indent=2)); return 0
    if cmd=='aggregate':
        r=load_json(sys.argv[2]); validate_eval(r); print(json.dumps(aggregate(r),ensure_ascii=False,indent=2)); return 0
    return 2
if __name__=='__main__': raise SystemExit(main())
