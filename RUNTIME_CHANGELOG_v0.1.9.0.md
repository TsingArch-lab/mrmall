# Runtime Changelog v0.1.9.0

## 目标
回退 v0.1.8.x 为 S007 引入的 Article Map / Argument Map / Rule Test Batch 复杂执行链，恢复简单的 Rule-first 批量审核结构；再依据最近的诊断假设，仅调整 S007 本身的语义边界与通用 Rule Evaluator 的执行纪律。

## 当前运行链
Article → Content Type → Applicable Rules → One Rule Batch Evaluator → Rule Results → Existing Gate → Feedback

事实搜索保持独立可选并行链，不参与创造内容判断标准。

## 本次内容语义变化
仅 S007 发生语义细化：
- “有新信息”不自动等于“有有效论证增量”。
- 新案例、新数字、新品牌、新抽象概念，只有改变/扩展/限定/推进核心理解才算增量。
- 多个段落即使各自有局部新信息，只要持续承担同一个已经充分完成的证明功能，仍可命中低推进。

其他 48 条 Rule 不变。

## Evaluator 通用执行纪律
不增加任何新内容标准，只要求模型：
- 每条 Rule 独立判断；
- 不得用“文章总体不错”替代逐 Rule 判断；
- PASS 不是默认值；先检查 fail_condition 与 exceptions；
- 一条 Rule PASS 不能作为另一条 Rule PASS 的理由；
- 全文关系 Rule 必须查看全文相关章节关系。

## 未改变
- Gate 与 v0.1.8.2 byte-identical。
- Severity / Gate aggregation 未改。
- Fact Search 标准与上限 8 未改。
- No Rule, No Feedback / No Rule, No Block / No Rule, No Penalty 未改。
