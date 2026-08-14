# v0.1.5.1 Hotfix

修复 Rule Evaluator 偶发返回 `FAIL` 但缺少 `match_explanation` 或 `article_evidence` 时，整篇审核被契约校验中止的问题。

## 修复原则

- 不放宽任何内容 Rule。
- 不改变 Gate、severity、PASS/FAIL 标准。
- 缺少 FAIL 必填依据时，不猜测补全，也不把它当作有效 FAIL。
- Runtime 将该 Rule 确定性降级为 `UNRESOLVED`，随后只对该 Rule 运行局部 Adjudicator。
- 若局部复核仍无法满足契约，则保持 UNRESOLVED，不阻塞整篇审核。

因此这是纯契约健壮性修复，不影响 v0.1.4 的论证尺度调整，也不影响 v0.1.5 的“值得保留”逻辑。
