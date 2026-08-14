# v0.1.2｜更新已有线上网站

你已经有 GitHub + Render + Vercel，不需要重新创建项目。

## 1. 更新 GitHub
用 v0.1.2 文件覆盖仓库中的同名文件并 Commit。

重点文件：
- `backend/app/llm.py`
- `backend/app/contracts.py`（新增）
- `backend/app/review_core.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `core/review_core/portable/prompts/01_rule_batch_evaluator.md`
- `core/review_core/portable/prompts/02_feedback_composer.md`
- `core/review_core/portable/prompts/04_router.md`
- `frontend/app.js`
- `frontend/index.html`

最省事的方式是用 v0.1.2 整包覆盖当前仓库内容。

## 2. Render
GitHub Commit 后 Render 正常会自动部署。

环境变量继续保留：
- `LLM_PROVIDER=openai_compatible`
- `LLM_API_KEY=你的 DeepSeek Key`
- `LLM_BASE_URL=https://api.deepseek.com`
- `LLM_MODEL=你当前实际使用的模型 ID`
- `APP_ACCESS_TOKEN=你的访问口令`
- `CORS_ORIGINS=*`
- `LLM_TIMEOUT_SECONDS=180`（建议）
- `LLM_HTTP_RETRIES=2`（建议）

不要开启 `LLM_DEBUG_RAW_RESPONSE`，除非排查模型协议问题；原始响应可能包含文章内容。

部署后打开：
`https://mrmall-api.onrender.com/health`

应看到：
- `"ok": true`
- `"version": "0.1.2"`
- `"provider": "openai_compatible"`
- `"model": "..."`

## 3. Vercel
同一个 GitHub Commit 会触发 Vercel 自动部署。

打开网页，标题上方应看到 `REVIEW CORE v0.1.2`。

## 4. 第一次真实测试
建议先在网页手动选择文章类型，例如 D，测试真实 Rule Evaluator。

成功后再切回“自动判断”，测试 Router。

这样如果失败，可以明确区分：
- Router问题；
- Rule Evaluator问题；
- Feedback Composer问题。

## 5. 如果仍报错
网页会直接显示后端的受控错误，例如：
- 自动判断失败：提示手动选择 A/B/C/D/E；
- Rule Evaluator 契约失败：中止本次审核，不输出错误结论；
- Provider 429/5xx：后端有限重试后返回明确错误。

Render Logs 不再需要依赖 Python traceback 才能判断错误阶段。
