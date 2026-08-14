from pathlib import Path
import subprocess,sys,json
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def run(cmd):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    print(p.stdout,end=''); print(p.stderr,end='',file=sys.stderr)
    if p.returncode: raise SystemExit(p.returncode)
run([sys.executable,'core/review_core/engine/compile_rules.py'])
run([sys.executable,'core/review_core/engine/validate_rule_source.py'])
# ASCII filenames for deploy-sensitive Rule files
for p in (ROOT/'core/review_core/rules').iterdir():
    if p.is_file():
        try: p.name.encode('ascii')
        except UnicodeEncodeError: raise SystemExit(f'Non-ASCII deploy-sensitive filename: {p.name}')
# Required paths
for rel in ['backend/app/main.py','frontend/index.html','core/review_core/registry/compiled_rule_registry.json','render.yaml']:
    if not (ROOT/rel).exists(): raise SystemExit(f'Missing: {rel}')
reg=json.loads((ROOT/'core/review_core/registry/compiled_rule_registry.json').read_text(encoding='utf-8'))
print(f"[PASS] preflight complete; rules={reg['rule_count']}; hash={reg['registry_semantic_hash']}")
