# Runtime Performance Patch v0.1.6.2

本版本只修改 Runtime / API / Frontend，不修改任何内容 Rules，也不修改 Gate 判断逻辑。

## 目标

解决长文章审核时单个 HTTP 请求持续数分钟，最终浏览器出现 `Failed to fetch` 的问题，并缩短非核心后处理耗时。

## 改动

1. Rule Evaluator 保持使用主模型 `LLM_MODEL`。
2. Strength Extractor 与 Feedback Composer 改为并行执行。
3. 增加可选 `LLM_MODEL_SECONDARY`，用于 Strength + Feedback；留空时自动复用主模型。
4. 次要阶段超时或失败时自动降级：Strength 返回空；Feedback 使用 Rule-grounded deterministic fallback。不会改变 Gate 或最终判断。
5. 增加整体阶段超时：Evaluator 240s、Router 90s、Adjudicator 90s（均可通过环境变量调整）。
6. 新增异步审核 Job API：网页提交后立即获得 job_id，再用短轮询读取进度和结果，避免浏览器与 Render 保持一个数分钟的长连接。
7. 页面展示真实阶段：规则审核、未决复核、汇总、整理问题清单与值得保留。
8. `/health` 增加 secondary_model 字段。

## 推荐 Render 环境变量

现有变量保留，并新增：

```text
LLM_MODEL_SECONDARY=deepseek-v4-flash
LLM_SECONDARY_TIMEOUT_SECONDS=90
LLM_EVALUATOR_STAGE_TIMEOUT_SECONDS=240
LLM_ROUTER_STAGE_TIMEOUT_SECONDS=90
LLM_ADJUDICATOR_STAGE_TIMEOUT_SECONDS=90
```

如果不设置 `LLM_MODEL_SECONDARY`，系统仍可运行，只是 Strength / Feedback 会继续使用主模型。
