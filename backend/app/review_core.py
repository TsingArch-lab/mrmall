from __future__ import annotations
import json, re, uuid
from pathlib import Path
from typing import Any
from .config import CORE_DIR, settings
from .llm import get_provider

REGISTRY = CORE_DIR / "registry" / "compiled_rule_registry.json"
GATES = CORE_DIR / "portable" / "runtime" / "gate_registry.json"
PROMPTS = CORE_DIR / "portable" / "prompts"

DIM_MAP={
    'TOPIC':'选题价值','EVIDENCE':'证据支撑','GLOBAL':'证据支撑','INSIGHT':'观点质量',
    'STRUCTURE':'结构逻辑','EXPRESSION':'表达质量','FINAL':'表达质量'
}

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def rules_by_id():
    return {r["rule_id"]: r for r in load_json(REGISTRY)["rules"]}

def applicable_rule_ids(content_type: str):
    gates = load_json(GATES)["gates"]
    out=[]
    for gate_name in ['TOPIC','EVIDENCE','INSIGHT','STRUCTURE','FINAL']:
        g=gates[gate_name]
        out += g.get('always',[])
        out += g.get('by_type',{}).get(content_type,[])
        out += g.get('all_expression',[])
    reg=rules_by_id(); seen=set(); final=[]
    for rid in out:
        if rid in seen or rid not in reg: continue
        r=reg[rid]
        if content_type in r.get('applies_to',[]) or 'ALL' in r.get('applies_to',[]):
            seen.add(rid); final.append(rid)
    return final

def compact_rules(content_type: str):
    reg=rules_by_id()
    keys=['rule_id','name','stage','severity','evaluation_question','pass_condition','fail_condition','exceptions']
    return [{k:reg[rid].get(k) for k in keys} for rid in applicable_rule_ids(content_type)]

def validate_eval(result: dict[str, Any], content_type: str):
    supplied=set(applicable_rule_ids(content_type))
    buckets=[]
    buckets += result.get('passed_rule_ids',[])
    buckets += result.get('na_rule_ids',[])
    buckets += [x['rule_id'] for x in result.get('failed_rules',[])]
    buckets += [x['rule_id'] for x in result.get('unresolved_rules',[])]
    unknown=set(buckets)-supplied
    if unknown: raise ValueError(f"Model returned unsupplied Rule IDs: {sorted(unknown)}")
    if len(buckets)!=len(set(buckets)): raise ValueError('A Rule appears in multiple status buckets.')
    missing=supplied-set(buckets)
    if missing: raise ValueError(f"Model omitted Rule IDs: {sorted(missing)}")

async def adjudicate_unresolved(article: str, content_type: str, eval_result: dict[str,Any]):
    unresolved=eval_result.get('unresolved_rules',[])
    if not unresolved:
        return eval_result
    unresolved_ids=[x['rule_id'] for x in unresolved]
    reg=rules_by_id()
    keys=['rule_id','name','stage','severity','evaluation_question','pass_condition','fail_condition','exceptions']
    target_rules=[{k:reg[rid].get(k) for k in keys} for rid in unresolved_ids]
    evaluator=(PROMPTS/'01_rule_batch_evaluator.md').read_text(encoding='utf-8')
    user=_render(evaluator,{
        'CONTENT_TYPE':content_type,
        'APPLICABLE_RULES_COMPACT':target_rules,
        'VERIFICATION_RESULTS':[],
        'ARTICLE':article,
    })
    provider=get_provider()
    result=await provider.generate_json('你是 TARGETED_ADJUDICATOR。只复核输入的 UNRESOLVED Rules，不得重审其他规则。',user)
    # Validate targeted output only against the targeted IDs.
    buckets=[]
    buckets += result.get('passed_rule_ids',[])
    buckets += result.get('na_rule_ids',[])
    buckets += [x['rule_id'] for x in result.get('failed_rules',[])]
    buckets += [x['rule_id'] for x in result.get('unresolved_rules',[])]
    if set(buckets)!=set(unresolved_ids) or len(buckets)!=len(set(buckets)):
        return eval_result  # fail-safe: preserve original UNRESOLVED state
    eval_result['passed_rule_ids'] += result.get('passed_rule_ids',[])
    eval_result['na_rule_ids'] += result.get('na_rule_ids',[])
    eval_result['failed_rules'] += result.get('failed_rules',[])
    eval_result['unresolved_rules'] = result.get('unresolved_rules',[])
    return eval_result

def aggregate(eval_result:dict[str,Any]):
    reg=rules_by_id(); fails=eval_result.get('failed_rules',[])
    fail_ids=[x['rule_id'] for x in fails]
    by_stage={}
    for rid in fail_ids:
        r=reg[rid]; by_stage.setdefault(r['stage'],[]).append(r)
    revise=False
    if any(reg[rid]['severity']=='BLOCKER' for rid in fail_ids): revise=True
    if eval_result['content_type'] in {'A','B'} and len(by_stage.get('TOPIC',[]))>=2: revise=True
    for stage in ['STRUCTURE','FINAL']:
        if sum(1 for r in by_stage.get(stage,[]) if r['severity']=='MAJOR')>=3: revise=True
    final='需要修改' if revise else '可以继续'
    dims={k:'达标' for k in ['选题价值','证据支撑','观点质量','结构逻辑','表达质量']}
    for rid in fail_ids:
        stage=reg[rid]['stage']; dim=DIM_MAP.get(stage)
        if dim: dims[dim]='有明显问题'
    return {'final_judgement':final,'dimension_states':dims,'failed_rule_ids':fail_ids}

def _render(template: str, values: dict[str, Any]):
    for k,v in values.items():
        if not isinstance(v,str):
            v=json.dumps(v,ensure_ascii=False,indent=2)
        template=template.replace('{{'+k+'}}',v)
    return template

def validate_feedback(feedback: dict[str,Any], eval_result: dict[str,Any]):
    failed={x['rule_id'] for x in eval_result.get('failed_rules',[])}
    if feedback.get('final_judgement') not in {'可以继续','需要修改','建议停止'}:
        raise ValueError('Invalid feedback final_judgement')
    negative=[]
    if feedback.get('core_diagnosis'): negative.append(feedback['core_diagnosis'])
    negative += feedback.get('issue_candidates',[])
    if not failed and negative:
        raise ValueError('No Rule, No Feedback violation: negative feedback exists with zero FAIL Rules')
    for item in negative:
        support=set(item.get('supporting_rule_ids',[]))
        if not support or not support.issubset(failed):
            raise ValueError(f"Feedback provenance violation: {support} is not subset of FAIL Rules {failed}")
        if not item.get('article_evidence'):
            raise ValueError('Feedback item missing article evidence')

def registry_hash():
    return load_json(REGISTRY).get('registry_semantic_hash','unknown')

async def route_content_type(article: str) -> str:
    provider=get_provider()
    prompt=(PROMPTS/'04_router.md').read_text(encoding='utf-8')
    system=prompt.split('---')[0]
    user=prompt + '\n\nARTICLE:\n' + article
    data=await provider.generate_json(system,user)
    c=data.get('content_type')
    if c not in {'A','B','C','D','E'}:
        raise ValueError(f"Invalid content type from router: {c}")
    return c

async def review_article(article: str, content_type: str, verify_facts: bool=False):
    if content_type == 'AUTO':
        content_type = await route_content_type(article)
    provider=get_provider()
    rules=compact_rules(content_type)
    evaluator=(PROMPTS/'01_rule_batch_evaluator.md').read_text(encoding='utf-8')
    verification_note = None
    verification_results = []
    if verify_facts:
        verification_note = 'Web v0.1.1 尚未接入外部事实检索插件；本次不会伪造事实核验结果。'
    eval_user=_render(evaluator,{
        'CONTENT_TYPE':content_type,
        'APPLICABLE_RULES_COMPACT':rules,
        'VERIFICATION_RESULTS':verification_results,
        'ARTICLE':article,
    })
    eval_result=await provider.generate_json('你是严格的 Rule Executor，只能执行输入 Rules。', eval_user)
    eval_result['content_type']=content_type
    validate_eval(eval_result,content_type)
    eval_result=await adjudicate_unresolved(article,content_type,eval_result)
    validate_eval(eval_result,content_type)
    agg=aggregate(eval_result)

    feedback_prompt=(PROMPTS/'02_feedback_composer.md').read_text(encoding='utf-8')
    failed=eval_result.get('failed_rules',[])
    if failed:
        fb_user=_render(feedback_prompt,{
            'FINAL_JUDGEMENT':agg['final_judgement'],
            'DIMENSION_STATES':agg['dimension_states'],
            'FAILED_RULES_ONLY':failed,
            'VERIFICATION_RESULTS':verification_results,
            'PASSED_STRENGTH_CANDIDATES':[],
        })
        feedback=await provider.generate_json('你是 Feedback Composer，不得新增审稿标准。',fb_user)
        feedback['final_judgement']=agg['final_judgement']
        validate_feedback(feedback,eval_result)
    else:
        feedback={
            'final_judgement':agg['final_judgement'],
            'dimension_assessments':agg['dimension_states'],
            'core_diagnosis':None,
            'issue_candidates':[],
            'strengths':['没有触发当前 Rules 定义的阻塞性问题。'] if settings.llm_provider!='mock' else ['MOCK 模式：网站链路已跑通；此结果不是实际审稿结论。'],
        }

    return {
        'review_id':str(uuid.uuid4()),
        'content_type':content_type,
        'final_judgement':agg['final_judgement'],
        'dimension_states':agg['dimension_states'],
        'core_diagnosis': feedback.get('core_diagnosis',{}).get('text') if feedback.get('core_diagnosis') else None,
        'issues': feedback.get('issue_candidates',[]),
        'strengths': feedback.get('strengths',[]),
        'unresolved_rules':eval_result.get('unresolved_rules',[]),
        'failed_rule_ids':agg['failed_rule_ids'],
        'model_provider':settings.llm_provider,
        'model':settings.llm_model or 'mock',
        'registry_hash':registry_hash(),
        'verification_note':verification_note,
    }
