# Runtime Changelog v0.1.8.1

- Article Representation Layer 从摘要型 Article Map 改为**保真 Argument Map**。
- 原文先由确定性程序按作者段落/标题边界切成 Argument Blocks；LLM 不再负责切分文章。
- 禁止 LLM 因“相同功能/相似语义”合并、删除或重排 Block。
- 每个 source Block 必须在 Map 中保留；即使 LLM 漏标，normalizer 也会补成中性 unit，避免结构信息消失。
- Map unit 新增 `block_id`、`paragraph_ids`、`source_excerpt`，用于全文型 Rules 精确回到原文。
- S007 执行提示强化为逐 Block 横向比较、删除测试与案例边际价值测试；未新增任何内容标准。
- I005/F003 的执行提示强化对强确定性表达与实际支撑链的对应检查；未改变 Rule 原文。
- DIRECT_TEXT 与 Argument Map 生成继续并行；MAP_AWARE Rules 仍一次批量执行，不增加 per-Rule LLM 调用。
- 默认 `ARTICLE_MAP_MAX_UNITS` 从 18 提高到 40，仅作为极端长文的机械安全上限；不是内容规则。
- 49 条 Rules 未修改；Gate、Gate Registry 未修改。
