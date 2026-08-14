# v0.1.2 上线前审计

## 已修复
1. Router 返回 `None`：强契约 + 归一化 + 一次定向重试。
2. Markdown JSON code fence 解析：修复 v0.1.1 正则错误。
3. OpenAI-compatible 不支持 `response_format`：400/404/422 时自动去掉 JSON mode 重试。
4. 网络/限流/服务错误：408/429/5xx 有限重试。
5. Rule Evaluator 漏 Rule、重复 Rule、未知 Rule：严格拒绝。
6. FAIL 没有文章证据或 match explanation：严格拒绝，防止伪 FAIL。
7. Evaluator 轻微字段名偏差：有限归一化；实质缺失不猜。
8. Feedback Composer 格式失败：确定性 fallback，只使用真实 FAIL Rule。
9. Feedback 修改程序最终判断：拒绝。
10. Raw response 日志：默认关闭，避免稿件内容泄漏。
11. API 错误分类：模型/协议 502，契约/验证 422，未知错误 500。

## 有意保留的边界
- 无法保证任意第三方所谓“OpenAI-compatible API”都完全兼容。
- 不对模型的判断正确率做程序性保证；系统保证的是“不允许越过 Rules”和“不接受坏格式伪装成有效结果”。
- 事实搜索插件仍未接入。
- Free Render 冷启动仍可能造成首个请求较慢。
- 如果 DeepSeek 当前模型 ID 填错，Provider 会返回官方 4xx；这是配置错误，不是 Review Core 错误。

## Fail-safe 原则
宁可中止一次审核，也不把格式错误、缺 Rule、缺证据的模型输出当作真实审稿结论。
