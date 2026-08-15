# Internal Test v0.1.9.0

## Engineering status: PASS
- 49 Rules successfully compiled.
- Only S007 semantic hash changed relative to v0.1.7.2 simple baseline.
- Gate YAML and gate_registry.json are byte-identical to v0.1.8.2.
- Active review_core contains no Article Map / Execution Plan / MAP_AWARE path.
- Response contract test PASS.
- Mock review integration PASS.
- Runtime regression PASS.

## Semantic production status: PENDING
本地环境没有生产 DeepSeek API Key，因此不能把工程测试等同于生产语义测试。

上线后的最小诊断实验：
1. 用 CPI 修改前版本跑完整 Batch；观察 S007 / I005 / F003。
2. 用 CPI 修改后版本跑完整 Batch，防止 S007 过度触发。
3. 如果旧 CPI 仍然 S007 PASS，再进行“同一全文 + 仅 S007 单 Rule”的生产对照实验：
   - 单 Rule FAIL、Batch PASS → 批处理注意力/总体印象污染；
   - 单 Rule仍 PASS → S007 语义仍需继续校准；
   - 不再先改架构。
