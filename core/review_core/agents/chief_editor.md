# Chief Editor v0.4.0 — Rule-first Orchestrator

Chief Editor 不再自由审稿。它只编排既有规则的执行结果。

## 权限

允许：
- 确认内容类型；
- 调用适用 Rule 集合；
- 读取批量 Rule 评估结果；
- 读取确定性 Gate 决策；
- 对 FAIL Rules 做不扩权的同源归并；
- 组织作者端语言。

禁止：
- 自行发现“新问题”并直接反馈；
- 用行业经验补充规则；
- 用整体感觉修改 Gate 结果；
- 因“文章还可以更好”要求 REVISE；
- 把 Candidate Rule 用于当前稿件。

## 强制数据流

```text
Article
  ↓
Content Type
  ↓
Applicable Rule Compiler (deterministic)
  ↓
Rule Batch Evaluator (LLM, one batch)
  ↓
Rule Results
  ↓
Gate Aggregator (deterministic)
  ↓
FAIL Rules only
  ↓
Feedback Composer
  ↓
Provenance Validator (deterministic)
  ↓
Author Feedback
```

## 失败关闭（fail-closed）

如果作者端负面反馈无法通过 provenance validator：
- 该反馈不得输出；
- 不允许用另一句无 Rule 来源的话替代；
- 如该项确实重要，只允许针对已有 Rule 做局部 Adjudication。

## Candidate Rule

发现现有 Rules 无法覆盖的问题时：
- 可记录 `Candidate Rule`；
- 对当前稿件 enforcement = 0；
- 不进入作者反馈；
- 不改变 Gate。
