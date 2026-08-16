# PATCH INSTRUCTIONS — v0.1.12.0

Apply this patch on top of the deployed v0.1.11.0 runtime.

Overwrite these files at the repository root:

1. `backend/app/review_core.py`
2. `core/review_core/portable/prompts/06_dimension_gate_evaluator.md`

Optional documentation:
- `RUNTIME_CHANGELOG_v0.1.12.0.md`

Then redeploy Render. No environment-variable changes are required, provided your existing secondary model is `deepseek-v4-flash`.

Expected runtime behavior after deployment:
- Router logs should use the secondary model internally.
- Main `evaluate_rules` remains on primary/Pro.
- Targeted UNRESOLVED and fact-sensitive adjudication use secondary/Flash.
- `dimension_gate` still uses Flash, but Dimension ownership is now fixed by Rule stage and cannot spread a FAIL into unrelated Dimensions.

Recommended regression order:
1. 陆家嘴：verify not all five Dimensions turn red merely because many FAILs exist.
2. 消费动机：especially watch 表达质量; X002 alone should not automatically make the whole Dimension fail unless its impact is substantial.
3. OPPO：verify a 0-FAIL good draft still returns all Dimensions 达标 / 可以继续.
