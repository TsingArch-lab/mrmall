# Runtime Changelog v0.1.11.0

## Goal
Stabilize post-Rule review architecture without changing editorial Rules or S005/S007 semantics.

## Architecture
After confirmed Rule results, three downstream tasks now run independently and concurrently:
1. Problem Clusterer — merges same-source FAILs into author-facing issues.
2. Dimension Evaluator — assesses whole-dimension impact from confirmed FAILs only.
3. Strength Extractor — extracts positive assets from eligible PASS Rules.

Gate no longer makes independent editorial judgements. Release state is derived only from Dimension:
- all five dimensions = 达标 -> 可以继续
- any dimension = 有明显问题 -> 需要修改

## BLOCKER
BLOCKER no longer directly triggers Gate. Instead, any confirmed BLOCKER FAIL must force its mapped Dimension to 有明显问题. The deterministic release mapping then produces 需要修改.

## FINAL meta rules
F001 and F002 are no longer sent to the model as fresh article judgements.
- F001 is deterministically derived from already-confirmed upstream BLOCKER FAILs.
- F002 is deterministically PASS when runtime severity execution is structurally valid.
They are excluded from author-facing problem clustering and Dimension provenance.
F003 remains a normal content Rule.

## Problem feedback resilience
Feedback now uses item-level validation. One malformed issue no longer invalidates the whole response. Invalid items are dropped; if no valid model items remain, deterministic cluster fallback is used.

## Output consistency
A finished draft cannot return 需要修改 with zero author-facing issues when confirmed user-facing FAIL Rules exist. Deterministic clustered fallback fills the issue list.

## Logging
Adds:
- post-adjudication failed_ids / unresolved_ids
- final Rule result failed_ids / unresolved_ids after derived meta rules
- Dimension input failed IDs
- Dimension states and release result

## Unchanged
- Human Rules / Registry semantics
- S005 / S007
- FAIL-FIRST evaluator discipline
- Strength rules
- Fact Search
- Router
- benchmark samples
