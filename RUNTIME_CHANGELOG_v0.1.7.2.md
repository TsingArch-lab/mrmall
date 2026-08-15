# Runtime / Fact Search Changelog v0.1.7.2

- Fact Claim Extractor 按用户新标准重排事实搜索优先级。
- 基础锚点、具名故事、人物引语、权威归属成为主要搜索对象。
- 一般经营数据和营销型极值不再天然高优先级。
- 明示为项目方内部、无公开来源线索的经营数据不进入搜索队列。
- 新增 `risk_tag`；权威归属的 `questionable/contradicted` 结果增加 `authority_warning` 前端重点提示。
- Fact Search 上限仍为 8。
- 延续 v0.1.7.1 的 Fact Search / Rule Evaluator 并行运行。
- No content Rule changes.
- No Gate changes.
