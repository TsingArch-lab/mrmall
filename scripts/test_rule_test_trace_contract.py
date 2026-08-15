from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.contracts import normalize_rule_evaluation
raw={
 'content_type':'A','evaluated_rule_ids':['S007'],'passed_rule_ids':['S007'],
 'failed_rules':[],'na_rule_ids':[],'unresolved_rules':[],
 'test_trace':{'batch_name':'ARGUMENT_PROGRESSION','operations_completed':['deletion_test'],
               'observations':[{'rule_id':'S007','signals':['B1/B2']}]} }
out=normalize_rule_evaluation(raw,content_type='A',supplied_rule_ids=['S007'])
assert 'test_trace' not in out
assert out['passed_rule_ids']==['S007']
print('[PASS] test_trace is stripped before Rule Result / Gate')
