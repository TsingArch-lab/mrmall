# 上线前审计 v0.1.1

## 已修复的高风险问题
1. 中文 Rule 文件名在 Windows 解压后乱码 → 全部 ASCII 文件名。
2. Render `rootDir=backend` 会导致 `core/` 在运行时不可用 → Root Directory 留空。
3. 替换 MD 后 Registry 可能不自动更新 → Render build 阶段强制 compile + validate。
4. 付费模型 API 裸奔可能被外部滥用 → 增加 APP_ACCESS_TOKEN，前端支持 Bearer Token。
5. 模型偶发返回非法 JSON 导致 500 → 增加一次仅格式修复重试。
6. UNRESOLVED 没有进入局部复核 → 增加 targeted adjudication。
7. 包内含 pycache/pyc → 清除并加入 .gitignore。
8. Docker 固定 8000 端口 → 支持 PORT 环境变量。

## 仍然是 MVP 限制，不属于部署故障
- 事实搜索暂未接入。
- 没有数据库与历史稿件。
- 没有正式账号系统；APP_ACCESS_TOKEN 只适合单人/小团队测试。
- OpenAI-compatible Adapter 无法保证所有供应商完全一致；首次换模型需要跑回归测试。
- 超长文章会受具体模型上下文限制；当前先限制为 50,000 字符。
- “值得保留”仍主要依赖 Feedback Composer，后续应增加更严格的正向 provenance。

## 上线顺序
先 MOCK → 再真实模型 → 再收紧 CORS → 再考虑数据库/登录/事实检索。
