#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json, re, hashlib, sys, yaml
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "rules"
INDEX = RULES_DIR / "source_index.yaml"
OUT = ROOT / "registry" / "compiled_rule_registry.json"

VALID_SEVERITIES = {"BLOCKER","MAJOR","MINOR","INFO","NA"}
RULE_RE = re.compile(r"^###\s+([A-Z][A-Z0-9_]*\d{2,4})\s*[｜|]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
ALIASES = {
    "Stage":"stage", "适用类型":"applies_to", "严重级别":"severity",
    "判定问题":"evaluation_question", "通过条件":"pass_condition",
    "失败条件":"fail_condition", "例外":"exceptions",
}

def semantic_hash(obj):
    payload = {k: obj[k] for k in [
        "rule_id","source_file","source_section","name","stage","applies_to",
        "severity","evaluation_question","pass_condition","fail_condition","exceptions"
    ]}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",",":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

def parse_value(field, lines):
    text = "\n".join(lines).strip()
    if field == "applies_to":
        return [x.strip() for x in re.split(r"[/、,，]", text) if x.strip()]
    if field == "exceptions":
        vals=[]
        for ln in lines:
            m=re.match(r"^\s*[-*]\s+(.*)$", ln)
            if m and m.group(1).strip()!="无":
                vals.append(m.group(1).strip())
        return vals
    return text

def parse_file(path):
    lines=path.read_text(encoding="utf-8").splitlines()
    out=[]; current_section=""; i=0
    while i<len(lines):
        if lines[i].startswith("## ") and not lines[i].startswith("### "):
            current_section=lines[i][3:].strip(); i+=1; continue
        m=RULE_RE.match(lines[i])
        if not m:
            i+=1; continue
        rid,name=m.groups(); i+=1
        fields={}; field=None; buf=[]
        def flush():
            nonlocal buf,field
            if field is not None:
                fields[field]=parse_value(field,buf)
            buf=[]
        while i<len(lines):
            if RULE_RE.match(lines[i]) or (lines[i].startswith("## ") and not lines[i].startswith("### ")):
                break
            fm=FIELD_RE.match(lines[i].strip())
            if fm and fm.group(1) in ALIASES:
                flush(); field=ALIASES[fm.group(1)]
            elif field is not None:
                buf.append(lines[i])
            i+=1
        flush()
        required=["stage","applies_to","severity","evaluation_question","pass_condition","fail_condition","exceptions"]
        missing=[x for x in required if x not in fields]
        if missing:
            raise ValueError(f"{path.name} {rid}: missing {missing}")
        sev=fields["severity"].strip().upper()
        if sev not in VALID_SEVERITIES:
            raise ValueError(f"{path.name} {rid}: invalid severity {sev}")
        obj={
            "rule_id":rid, "source_file":path.name, "source_section":current_section,
            "name":name.strip(), "stage":fields["stage"].strip(),
            "applies_to":fields["applies_to"], "severity":sev,
            "evaluation_question":fields["evaluation_question"],
            "pass_condition":fields["pass_condition"],
            "fail_condition":fields["fail_condition"],
            "exceptions":fields["exceptions"],
        }
        obj["semantic_hash"]=semantic_hash(obj)
        obj["execution"]={
            "output_on_pass":"ID_ONLY",
            "output_on_fail":"EVIDENCE_AND_MATCH_ONLY",
            "allowed_feedback_meaning":obj["fail_condition"],
            "may_create_new_criterion":False,
        }
        out.append(obj)
    return out

def main():
    idx=yaml.safe_load(INDEX.read_text(encoding="utf-8"))
    all_rules=[]; seen={}
    for fn in idx["executable_rule_files"]:
        p=RULES_DIR/fn
        if not p.exists(): raise FileNotFoundError(fn)
        for r in parse_file(p):
            if r["rule_id"] in seen:
                raise ValueError(f"Duplicate Rule ID {r['rule_id']}: {seen[r['rule_id']]} / {fn}")
            seen[r["rule_id"]]=fn; all_rules.append(r)
    if not all_rules: raise RuntimeError("No executable Rules found.")

    stage_order={"GLOBAL":0,"ROUTER":1,"TOPIC":2,"EVIDENCE":3,"INSIGHT":4,"STRUCTURE":5,"EXPRESSION":6,"FINAL":7}
    all_rules.sort(key=lambda r:(stage_order.get(r["stage"],99),r["rule_id"]))
    reg_hash="sha256:"+hashlib.sha256("\n".join(r["semantic_hash"] for r in all_rules).encode()).hexdigest()
    data={
        "schema_version":"1.1",
        "content_semantics_version":"0.4.1-md-source",
        "runtime_version":"0.4.1",
        "single_source_of_truth":"rules/*.md",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "rule_count":len(all_rules),
        "rules":all_rules,
        "registry_semantic_hash":reg_hash
    }
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"[PASS] Compiled {len(all_rules)} Rules from Markdown.")
    print(f"[PASS] Registry hash: {reg_hash}")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print(f"[RULE-COMPILER-ERROR] {e}",file=sys.stderr); sys.exit(1)
