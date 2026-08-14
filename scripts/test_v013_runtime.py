import os,sys,asyncio
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['LLM_PROVIDER']='mock'
from app.contracts import normalize_rule_evaluation
from app.verification import VerificationContext
from app.feedback_clustering import cluster_failed_rules
raw={"content_type":"D","evaluated_rule_ids":["G001","I005"],"passed_rule_ids":["I005"],"failed_rules":[{"rule_id":"G001","article_evidence":["日本健身支出相关描述"],"match_explanation":"该关键事实未提供可追溯来源，当前无法核实。"}],"na_rule_ids":[],"unresolved_rules":[]}
out=normalize_rule_evaluation(raw,content_type='D',supplied_rule_ids=['G001','I005'],verification_context=VerificationContext('NOT_RUN',[]))
assert out['failed_rules']==[] and out['unresolved_rules'][0]['rule_id']=='G001'
raw2={"content_type":"D","evaluated_rule_ids":["G001"],"passed_rule_ids":[],"failed_rules":[{"rule_id":"G001","article_evidence":["同一事件前文写2025，后文写2023"],"match_explanation":"文章内部时间自相矛盾，属于事实冲突。"}],"na_rule_ids":[],"unresolved_rules":[]}
out2=normalize_rule_evaluation(raw2,content_type='D',supplied_rule_ids=['G001'],verification_context=VerificationContext('NOT_RUN',[]))
assert out2['failed_rules'][0]['rule_id']=='G001'
registry={"E003":{"name":"a","fail_condition":"x"},"I006":{"name":"b","fail_condition":"y"},"S004":{"name":"c","fail_condition":"z"},"F001":{"name":"d","fail_condition":"runtime"}}
fails=[{"rule_id":"E003","article_evidence":["A"],"match_explanation":"a"},{"rule_id":"I006","article_evidence":["A"],"match_explanation":"b"},{"rule_id":"S004","article_evidence":["B"],"match_explanation":"c"},{"rule_id":"F001","article_evidence":["X"],"match_explanation":"gate"}]
c=cluster_failed_rules(fails,registry)
assert len(c)==1 and set(c[0]['supporting_rule_ids'])=={'E003','I006','S004'}
from app.review_core import review_article
res=asyncio.run(review_article('这是一篇测试文章。作者讨论商业地产经营压力和个人反思。'*10,'AUTO',False))
assert res['model_provider']=='mock'
assert '外部事实核验未执行' in res['verification_note']
print('[PASS] v0.1.3 runtime regression')
