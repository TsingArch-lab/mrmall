# Mall Content OS v0.1.11.0 Patch Instructions

Base requirement: deploy on top of the currently running v0.1.10.0 + FAIL-FIRST runtime.

Copy/overwrite these files using the same relative paths:

1. `backend/app/review_core.py`
2. `core/review_core/portable/prompts/01_rule_batch_evaluator.md`
3. `core/review_core/portable/prompts/02_feedback_composer.md`
4. `core/review_core/portable/prompts/06_dimension_gate_evaluator.md` (new file)
5. `RUNTIME_CHANGELOG_v0.1.11.0.md` (new documentation file)

No environment-variable changes are required.
No Rules or compiled Registry files are changed.
No Gate Registry file is changed; legacy gate_registry remains only for selecting applicable Rules, not for final release aggregation.

After commit/push and Render redeploy, verify logs contain:
- `[review] rule_results final failed_ids=...`
- `[review] problem_clusterer start ...`
- `[review] dimension_gate start ... input_failed_ids=...`
- `[review] dimension_gate done ... final=... states=...`

Expected product invariant:
- all dimensions 达标 -> 可以继续
- any dimension 有明显问题 -> 需要修改
- BLOCKER FAIL -> mapped dimension 有明显问题 -> 需要修改
- Problem Clusterer failure must not force all dimensions back to 达标.
