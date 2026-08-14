# Test Status v0.1.1

已完成：
- 48条 Markdown Rules 编译通过；
- Rule Source Validator 通过；
- 所有 Rule 文件名为 ASCII、内容 UTF-8；
- Python 语法检查通过；
- JSON/YAML 解析通过；
- FastAPI `/health` 本地 TestClient 返回 200；
- FastAPI `/api/review` 在 MOCK 模式返回 200；
- AUTO Router MOCK 链路通过；
- APP_ACCESS_TOKEN 正确拦截无口令/错误口令，并允许正确口令；
- Registry hash 可正常返回。

尚未完成：
- Render 真实云端部署；
- Vercel 真实云端部署；
- 真实付费模型 API 的端到端回归；
- 外部事实搜索插件（本版本未实现）。
