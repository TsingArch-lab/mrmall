# Mall Content OS Web v0.1.1｜第一次上线教程

## 0. GitHub 仓库应当长这样
仓库根目录直接看到：`backend/`、`core/`、`frontend/`、`render.yaml`。不要再套一层项目文件夹。

## 1. 先部署 Render 后端
1. 登录 Render，New → Web Service，连接 GitHub 仓库。
2. **Root Directory 留空。** Review Core 在根目录 `core/`，不能把 Root Directory 设置为 `backend`。
3. Build Command：
   `pip install -r backend/requirements.txt && python core/review_core/engine/compile_rules.py && python core/review_core/engine/validate_rule_source.py`
4. Start Command：
   `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Health Check Path：`/health`
6. 第一轮环境变量只设置 `LLM_PROVIDER=mock`、`CORS_ORIGINS=*`。
7. 部署成功后打开 `https://你的地址.onrender.com/health`，应看到 `ok: true`。

## 2. 再部署 Vercel 前端
1. Vercel → Add New Project → Import 同一个 GitHub 仓库。
2. Root Directory 设置为 `frontend`。
3. Framework Preset 选择 Other / Static（如果 Vercel 自动识别可保持默认）。
4. Deploy。
5. 打开网页，把 Render API 地址填入“后端 API 地址”。

## 3. MOCK 跑通后再接付费模型
在 Render Environment 中设置：
- `LLM_PROVIDER=openai_compatible`
- `LLM_API_KEY=你的密钥`
- `LLM_BASE_URL=供应商 OpenAI-compatible API 根地址`
- `LLM_MODEL=模型名`
- `APP_ACCESS_TOKEN=你自己生成的一串长随机字符`

然后在网页“访问口令”里输入同一 `APP_ACCESS_TOKEN`。**不要把模型 API Key 填到网页。**

## 4. 上线后收紧 CORS
拿到 Vercel 正式网址后，把 Render 的 `CORS_ORIGINS=*` 改为完整网址，例如：
`https://your-project.vercel.app`

## 5. Rules 更新
直接替换 `core/review_core/rules/*.md` 后提交 GitHub。Render 下一次部署会自动：
1. 编译 Markdown Rules；
2. 校验 Rule Source；
3. 生成新的 Registry。

## 6. 现阶段明确未包含
- 数据库 / 历史稿件
- 多用户登录
- 外部事实搜索插件
- 自动保存审稿结果

先验证核心审核闭环。
