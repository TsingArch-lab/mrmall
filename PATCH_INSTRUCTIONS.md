# Mall Content OS v0.1.13.0 Patch Instructions

Base: v0.1.12.0

Upload/overwrite these files at the same relative paths:

- `backend/app/review_core.py`
- `core/review_core/portable/prompts/02_feedback_composer.md`
- `core/review_core/portable/prompts/06_dimension_gate_evaluator.md`
- `frontend/app.js`

Then redeploy backend and frontend if your platform does not auto-deploy on commit.

## What changed

1. Frontend no longer displays Rule IDs / Rule detail under problems or strengths.
2. Frontend author-facing text no longer uses `FAIL Rule`, `PASS`, `BLOCKER`, `Gate` and similar internal terminology.
3. When fact verification is not run, frontend only shows: `外部事实核验未执行。`
4. Dimension calibration is stricter about release threshold: a single non-BLOCKER local FAIL does not by itself make the whole Dimension fail. The Dimension becomes `有明显问题` only when the confirmed issue reaches the core/major scope or requires substantive rework.
5. Backend provenance (`supporting_rule_ids`) is preserved unchanged for logs/debugging; only frontend rendering hides it.

No changes to Rules, Rule Evaluator, fixed Rule→Dimension ownership, Gate derivation, Router/Adjudicator model split, Fact Search, or Strength eligibility.
