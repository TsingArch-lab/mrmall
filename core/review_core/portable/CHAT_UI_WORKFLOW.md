# 无 API / 普通聊天界面运行方式

适用于 Claude 网页版、ChatGPT、Gemini、豆包、Kimi、通义等只能上传文件/粘贴文本的环境。

## 准备
上传：
1. `registry/compiled_rule_registry.json`
2. `portable/runtime/gate_registry.json`
3. `portable/schemas/rule_evaluation_schema.json`
4. 待审核文章
5. 如需事实核验，再提供检索结果或使用平台自带搜索。

## 第一次对话：Rule Evaluation
复制 `portable/prompts/01_rule_batch_evaluator.md`，填入文章类型、适用 Rules 和文章。
保存模型返回 JSON。

## 本地/人工确定性步骤
不得让模型凭整体感觉决定 Gate。使用 `portable/reference_runtime.py` 或按 `runtime_spec.json` 聚合。

## 第二次对话：Feedback Composition
只把第一次结果中的 `failed_rules`、程序确定的判断与分项状态交给模型。复制 `02_feedback_composer.md`。

## 最后一步
运行 provenance validator。任何没有真实 FAIL Rule 支持的问题都删除。

## 没有搜索功能怎么办
可以审结构、观点、证据链与表达；对于无法由用户材料确认的外部事实，不得伪造搜索结果。必要时保留为 UNRESOLVED / 未核验，不因“没搜到”自动 FAIL。
