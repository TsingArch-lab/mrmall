# Runtime Changelog v0.1.10.0

## Rule / Dimension 分层

架构变为：

`Article → Rule Evaluator → Rule Results → Gate`  
`                              ↘ Dimension Impact → 五维`  
`                              ↘ Feedback / Strengths`

### Rule 层
- 采用非抵消式 FAIL-FIRST。
- 先确认是否完整命中 `fail_condition`。
- 局部症状不等于完整 FAIL。
- 完整命中且无 exception 时直接 FAIL；不得用其他优点抵消。

### Dimension 层
- Rule FAIL 是 criterion-level judgement，不等于 whole-dimension judgement。
- 五维只能基于已验证 FAIL Rules 做影响聚合。
- 无 FAIL 的维度必须“达标”。
- 有 FAIL 的维度可根据问题影响范围判“达标”或“有明显问题”。
- 该层不影响 Gate。

### Gate
- 无变化。

### 性能
- 不新增模型调用。Dimension impact 合并进原有 Feedback Composer secondary-model 调用。
