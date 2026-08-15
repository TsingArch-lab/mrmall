# Runtime Changelog v0.1.8.2

## Purpose
把 v0.1.8.1 的单个 MAP_AWARE 大批量判断，升级为 Rule Execution Architecture v2：按现有 Rule 所需的认知操作分组执行，提升 Rule 真正被执行的概率，同时保持 Gate / Rules 完全不变。

## Changes
- Article Representation Layer 保持 v0.1.8.1 的保真 Argument Map，不再继续调整 Map 语义。
- MAP_AWARE Rules 被确定性分成最多 3 个 Rule Test Batches：
  1. `ARGUMENT_PROGRESSION`
  2. `MECHANISM_DERIVATION`
  3. `CLAIM_EVIDENCE_STRENGTH`
- 每个 Rule 仍只执行一次；三组是已有 Rule 的精确分区，不新增、不复制、不遗漏 Rule。
- 三个 Test Batch 并行调用，避免增加串行审核深度。
- Test Plan 只规定“如何执行现有 Rule”，不新增 PASS/FAIL 标准。
- 新增可观测 `test_trace`：只写运行日志，进入契约归一化前即被丢弃，绝不进入 Rule Results / Gate。
- 日志新增每个 Batch 的 Rule IDs、耗时、FAIL/UNRESOLVED，以及模型返回的执行观察信号。

## Locked boundaries
- No content Rule changes.
- No Gate changes.
- No Gate aggregation changes.
- No Rule severity changes.
- Fact Search boundary unchanged.
