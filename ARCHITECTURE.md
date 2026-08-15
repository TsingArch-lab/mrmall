# Architecture｜Web v0.1.8.0

## Source of truth

内容质量标准仍然只有一条合法来源：

```text
Markdown Rules
→ Compiler
→ Registry
→ Runtime Rule Executors
→ Deterministic Gate
```

Article Map、Fact Search、Feedback、Strength 均无权创建 Rule 或改变 Gate 标准。

## Review runtime

```text
Raw Article
   │
   ├──────────────→ Router（AUTO only）
   │
   └→ Article Representation Layer
          └→ Article Map
              - core question / thesis
              - major argument units
              - evidence / mechanism
              - relation_to_prior
              - new_contribution（描述性）
              - fact-search candidates（联网核验开启时）

Content Type resolved
   │
   ├→ DIRECT_TEXT Rule Executor ───────────────┐
   │      （局部/文本型 Rules，立即启动）         │
   │                                           ├→ merge exact Rule results
   └→ Article Map ready                         │
          ├→ MAP_AWARE Rule Executor ──────────┘
          │      （跨单元/全文型 Rules）
          │
          └→ Fact Search（optional）
                 Tavily Search → Fact Verifier

Merged Rule Results
   ↓
Targeted adjudication（only UNRESOLVED / fact-sensitive recheck）
   ↓
Deterministic Gate（UNCHANGED）
   ↓
Strength + Feedback（parallel, non-gating）
   ↓
Response
```

## Article Map boundary

> **Map 负责看清文章，Rule 负责评价文章。**

Article Map 只能描述：文章在回答什么、主要单元在做什么、用了什么材料、单元之间是什么关系、相较前文新增了什么命题/关系/材料。

Article Map 不允许输出：PASS / FAIL、好坏、删改建议、严重级别、Gate 结果或任何新增内容标准。Map 与原文冲突时，Rule Executor 必须以原文为准；FAIL 的 `article_evidence` 仍必须来自原文。

## Execution plan

Runtime 仅按“执行所需上下文”把**现有 applicable Rules**分成两个互斥集合：

- `DIRECT_TEXT`：主要依赖局部原文、事实、引语、表达或明确位置关系；
- `MAP_AWARE`：需要跨章节/跨单元比较，Article Map 用于提高执行稳定性。

两个集合的并集必须严格等于当前 applicable Rule IDs；不得新增、遗漏或重复 Rule。

## Efficiency

- Article Map 与 Router（AUTO）并行。
- `DIRECT_TEXT` Rules 在 Article Map 仍生成时即可开始执行。
- Map 完成后，`MAP_AWARE` Rules 与 Fact Search 并行。
- 开启 Fact Search 时，优先复用 Article Map 同一轮生成的事实候选，避免再单独调用 Fact Claim Extractor；只有 Map 降级时才回退旧 extractor。
- Strength / Feedback 继续并行，均不影响 Gate。

## Gate invariance

v0.1.8.0 **不修改任何 Gate 文件、Gate Rule ID、threshold 或聚合逻辑**。本版只改变已有 Rules 获得文章上下文并被执行的方式。
