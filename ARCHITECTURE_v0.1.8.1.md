# Argument Map Architecture v0.1.8.1

## 目标
服务当前既有 Rules 的稳定执行，不增加任何 Gate Rule 或隐藏评价标准。

## 流程

```text
Raw Article
  ├─ deterministic paragraph/heading splitter ─→ Argument Blocks
  │                                                ↓
  │                                       descriptive LLM labels
  │                                                ↓
  │                                         Argument Map
  │                                                ├─ MAP_AWARE Rules
  │                                                ├─ Fact Search candidates
  │                                                └─ Strength context
  └──────────────────────────────────────────────→ DIRECT_TEXT Rules
```

## 核心不变量
- Map 负责“看清文章”，Rule 负责“评价文章”。
- 程序切分只依据段落、标题、长度安全边界；禁止根据语义相同而合并。
- 一块原文对应一个 Map unit；Block 不能因为 LLM 漏标而消失。
- Article 永远是最终 evidence source。
- Gate 不读取 Map 产生新标准，只接收既有 Rule 的 PASS/FAIL/NA/UNRESOLVED。
- Rules / Gate 本版均不修改。

## 为什么从摘要 Map 改成保真 Map
v0.1.8.0 允许“连续数段若承担同一功能可合并”。这会把 S007 需要识别的同义重复、同质证明、重复总结在表示层提前折叠掉。v0.1.8.1 删除语义合并权，把“切分”改为确定性程序，把 LLM 任务缩小为“逐块标注”。
