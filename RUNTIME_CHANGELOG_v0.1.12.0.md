# Runtime Changelog v0.1.12.0

## Goal
Stabilize Dimension ownership and move bounded auxiliary judgements from Pro to Flash, while keeping the core Rule Evaluator on Pro.

## Dimension ownership
Dimension no longer infers which quality dimension a FAIL may affect. Ownership is fixed by Rule classification/stage:
- TOPIC -> 选题价值
- EVIDENCE -> 证据支撑
- GLOBAL -> 证据支撑
- INSIGHT -> 观点质量
- STRUCTURE -> 结构逻辑
- EXPRESSION -> 表达质量
- FINAL -> 观点质量 (F001/F002 remain derived meta rules and are excluded; F003 belongs here)

Each confirmed FAIL belongs to one primary Dimension only. The Dimension Evaluator only judges whether the FAILs already assigned to that Dimension are severe enough to make the whole Dimension fail the finished-draft publishing standard. Cross-dimension spreading is prohibited.

BLOCKER semantics remain unchanged from v0.1.11.0: any confirmed BLOCKER forces its assigned Dimension to 有明显问题; Gate is then derived deterministically from Dimension states.

## Model allocation
Use Flash / secondary model for bounded auxiliary tasks:
- Content Type Router -> Flash
- Fact-sensitive subset adjudicator -> Flash
- UNRESOLVED targeted adjudicator -> Flash
- Problem Clusterer -> Flash (unchanged)
- Dimension Evaluator -> Flash (unchanged)
- Strength Extractor -> Flash (unchanged)

Keep Pro / primary model for:
- Rule Batch Evaluator
- Rule contract repair, because it repairs the primary evaluator output without changing substantive judgements

## Dimension input reduction
Dimension Evaluator receives grouped confirmed FAIL provenance only. It no longer receives the full article, reducing opportunity for fresh review or cross-dimension inference.

## Unchanged
- Human Rules and fail/pass semantics
- Rule count
- S005/S007
- FAIL-FIRST discipline
- Gate definition: all Dimensions 达标 -> 可以继续; any Dimension 有明显问题 -> 需要修改
- Strength logic
- Fact Search provider/search process
- Problem Clusterer timeout/fallback
