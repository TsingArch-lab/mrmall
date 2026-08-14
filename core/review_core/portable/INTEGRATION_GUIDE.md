# 集成指南：把 Review Core 接到任何大模型

## 核心原则

厂商模型只是“推理函数”，Rules、Gate、聚合、Provenance 都在模型外部。这样更换模型不会改变审稿标准。

## 标准接入流程

1. `python engine/compile_rules.py`
2. `python engine/validate_rule_source.py`
3. 已知稿件类型时：`python portable/reference_runtime.py compact-rules A`
4. 将文章 + compact rules 填入 `01_rule_batch_evaluator.md`。
5. 调用任意模型，要求返回 `rule_evaluation_schema.json`。
6. 本地校验 JSON；运行 `reference_runtime.py aggregate evaluation.json`。
7. 仅将 `failed_rules` + 确定性结果送入 `02_feedback_composer.md`。
8. 运行原有 `engine/provenance_validator.py`。
9. 渲染作者端固定模板。

## OpenAI / Anthropic / Gemini / 国内模型的差异放在哪里？

只放在 Adapter：

```text
Review Core
    ↓
LLMAdapter.generate()
    ↓
OpenAI / Claude / Gemini / DeepSeek / Qwen / GLM / local model
```

Adapter 只处理：认证、URL、model name、messages格式、structured output参数、重试。
Adapter 禁止包含：Rule解释、评分标准、Gate逻辑。

## 平台支持 JSON Schema
优先使用原生 structured output。

## 平台不支持 JSON Schema
把 Schema 附在 Prompt 中；返回后本地 JSON parse + schema validator。若失败，只重试格式，不得重新自由审稿。

## 平台上下文较小
不要塞原始 Markdown。只塞 `compact-rules` 输出。PASS只需返回ID。

## 平台能力较弱
把一次 Rule Batch 按 stage 分成 2—4 个 batch，但仍然遵守：一个 batch 多条 Rule，绝不一条 Rule 一次调用。

## 平台没有联网搜索
跳过事实核验插件，不允许模型凭记忆伪装核验。审核仍可运行；需要外部确认的事实交给后续核验器或人工。

## 可替换性测试
同一篇文章、同一 Registry，分别让两个模型输出 Rule Evaluation。比较的是 Rule ID PASS/FAIL/UNRESOLVED 差异，而不是比较自由评论。这使跨模型回归测试成为可能。
