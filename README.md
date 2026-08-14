# Mall Content OS Web v0.1.1

最小可部署版本：静态前端 + FastAPI 后端 + Review Core。

## 核心原则
- Markdown Rules 是唯一人工规则源。
- Build 时自动编译 Registry。
- LLM 只执行 Rule，不决定 Gate。
- No Rule, No Feedback。

## 本版本修复
- Rules 文件名全部改为 ASCII，避免 Windows/GitHub/Linux 中文文件名编码问题。
- Render Root Directory 必须留空，保证后端能访问根目录的 `core/`。
- 增加 build-time Rule compile/validate。
- 增加 API 访问口令支持。
- 增加一次 JSON 格式修复重试。
- 增加 UNRESOLVED targeted adjudication。
- 清理 `__pycache__` / `.pyc`。
- 增加上线前 `scripts/preflight.py`。

详见 `DEPLOY_FOR_BEGINNERS.md` 和 `PRELAUNCH_AUDIT.md`。
