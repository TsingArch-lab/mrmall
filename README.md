# Mall Content OS Web v0.1.2

Review Core 的公网最小可用版本。

## v0.1.2 重点
本版本专门加固真实 OpenAI-compatible / DeepSeek 模型返回格式：

- 修复 Markdown ```json code fence 解析 bug；
- Router 使用强 JSON 契约；
- 兼容 `type: "D类"`、嵌套 result 等常见 Router 轻微格式偏差；
- Router 契约失败后只允许一次定向重试；
- Rule Evaluator 增加字段归一化与全 Rule 覆盖校验；
- Rule Evaluator 契约失败后只允许一次“结构修复”，不得重新审稿；
- Feedback Composer 失败时采用确定性 FAIL Rule fallback，避免整次审核因格式问题中断；
- Provider 支持 JSON mode 不兼容回退；
- 408/429/5xx/网络错误有限重试；
- 原始模型响应日志默认关闭，防止文章内容泄漏；
- API 对模型错误返回 502、规则契约错误返回 422；
- 增加响应契约与 MOCK 集成测试。

## 部署
仓库根目录部署 Render；`frontend/` 部署 Vercel。

真实 DeepSeek 示例环境变量：

```text
LLM_PROVIDER=openai_compatible
LLM_API_KEY=<secret>
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=<your current DeepSeek model id>
APP_ACCESS_TOKEN=<your private site token>
CORS_ORIGINS=*
LLM_TIMEOUT_SECONDS=180
LLM_HTTP_RETRIES=2
```

不要把 `LLM_API_KEY` 提交到 GitHub。
