#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json,yaml,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    idx=yaml.safe_load((ROOT/"rules"/"source_index.yaml").read_text(encoding="utf-8"))
    reg=json.loads((ROOT/"registry"/"compiled_rule_registry.json").read_text(encoding="utf-8"))
    if reg.get("single_source_of_truth")!="rules/*.md":
        raise RuntimeError("single_source_of_truth mismatch")
    ids=[r["rule_id"] for r in reg["rules"]]
    if len(ids)!=len(set(ids)): raise RuntimeError("duplicate Rule IDs")
    expected=set(idx["executable_rule_files"])
    for r in reg["rules"]:
        if r["source_file"] not in expected: raise RuntimeError(f"unexpected source: {r['source_file']}")
        if not (ROOT/"rules"/r["source_file"]).exists(): raise RuntimeError(f"missing source: {r['source_file']}")
        if r.get("execution",{}).get("may_create_new_criterion") is not False:
            raise RuntimeError(f"runtime criterion expansion: {r['rule_id']}")
    print(f"[PASS] Markdown-only Rule source validated: {len(ids)} Rules.")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print(f"[RULE-SOURCE-ERROR] {e}",file=sys.stderr); sys.exit(1)
