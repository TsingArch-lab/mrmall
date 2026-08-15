# Runtime Changelog v0.1.8.0

## 目标

本版不新增、删除或修改任何 Content Rule，不修改任何 Gate 文件、Rule ID、threshold 或聚合逻辑。目标只有两个：

1. 让当前已有 Rules 获得与其认知尺度相匹配的执行上下文，尤其是需要全文横向比较的 Rules；
2. 尽量通过并行和复用降低 Article Map 带来的额外延迟。

## 新增：Article Representation Layer

新增共享中间表示 `Article Map`：

- core_question / thesis
- major argument units
- unit role
- exact anchor quote
- evidence used
- mechanism
- relation_to_prior
- new_contribution
- fact-search candidates（仅联网核验开启时）

核心边界：**Map 负责看清文章，Rule 负责评价文章。**

Article Map 不输出 PASS/FAIL，不决定问题严重度，不提供删改建议，不进入 Gate。

## Rule Execution Plan

现有 applicable Rules 被运行时拆成两个互斥集合：

- `DIRECT_TEXT`：主要依赖局部原文、事实、引语、表达或开头位置；
- `MAP_AWARE`：需要跨章节、跨案例或全文链条比较。

两个集合的并集严格等于当前 applicable Rule IDs，每条 Rule 只执行一次。

A/B 当前为：13 个 DIRECT_TEXT + 20 个 MAP_AWARE。

S007、S001、I005、I004、T001、T002、F003 等进入 MAP_AWARE；G001、S002、S003、X001-X006 等保留 DIRECT_TEXT。

这只是执行元数据，不改变任何 Rule 的 pass/fail condition。

## 并行策略

```text
Article Map ─────────────────────────┐
                                     ├→ MAP_AWARE Rules
DIRECT_TEXT Rules（无需等 Map）──────┤
                                     └→ Fact Search（optional）
```

- AUTO Router 与 Article Map 并行；
- 类型确定后，DIRECT_TEXT Rules 立即启动，不等待 Map；
- Map 完成后，MAP_AWARE Rules 与 Fact Search 并行；
- Strength / Feedback 继续并行。

## Fact Search 复用

开启联网核验时，Article Map 同一轮生成最多 8 条 fact candidates，直接交给 Tavily；正常路径不再额外调用 Fact Claim Extractor。

若 Article Map 失败，Fact Search 才回退 v0.1.7.2 的独立 claim extractor。既有事实优先级标准完全不变。

## Strength 冲突保护

Strength Extractor 现在同时读取：

- PASS Rules；
- Article Map；
- 当前 FAILED Rules 作为冲突 guard。

仍然只能从 PASS Rules 生成 Strength。FAILED Rules 不能生成负面反馈或新标准，只用于避免把局部优点夸大成已被 FAIL 否定的全文属性。

## Invariants

- Rules：49 条，语义 hash 不变；
- Registry semantic hash：`sha256:31f357cf5a64d476ca35c9d86287c18a870bac33d9ddd3efafc8ab507dfce2df`
- Gate registry：与 v0.1.7.2 byte-identical；
- `No Rule, No Feedback / No Rule, No Block / No Rule, No Penalty` 不变。
