# Changelog

## v0.4.1
- 7 个可执行规则文件正式落为 Markdown 唯一人工源。
- `good_examples.md`、`bad_examples.md` 保持 Markdown 参考库。
- 新增 MD → Registry 编译器与 source validator。
- 全量重建 Registry，防止幽灵规则。
- 支持 severity=NA 的非强制型规则。
- 运行时禁止 Registry / Gate / Agent 反向创造 Rule。

## v0.4.0

### Runtime architecture
- 从“治理约束”升级为真正的 Rule-first runtime。
- 完整稿件采用单次批量 Rule evaluation，而非逐 Rule/逐 Gate 模型调用。
- Feedback Composer 只接收 FAIL Rules。
- Gate aggregation 程序化，不允许 LLM 整体感觉改判。

### Provenance
- 新增 `compiled_rule_registry.json` 与 per-rule semantic hash。
- 新增 `provenance_validator.py`。
- 负面反馈引用 PASS/不存在 Rule 时直接拒绝。

### Cost control
- PASS ID-only。
- applicable rules deterministic filtering。
- targeted adjudication only。
- known content type skips Router model call。

### Semantic guarantee
- 本版本没有新增任何内容 Rule。
- 现有 Rules/Registry 的质量标准语义保持不变。