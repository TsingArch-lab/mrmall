# Patch Instructions — v0.1.8.2 → v0.1.9.0

将 Patch 包内文件按相同路径覆盖到 GitHub 仓库，然后触发 Render / Vercel 重新部署。

## 必须覆盖
- VERSION
- frontend/app.js
- backend/.env.example
- backend/app/config.py
- backend/app/fact_search.py
- backend/app/llm.py
- backend/app/main.py
- backend/app/review_core.py
- core/review_core/engine/review_runtime.yaml
- core/review_core/portable/prompts/01_rule_batch_evaluator.md
- core/review_core/portable/prompts/05_strength_extractor.md
- core/review_core/rules/structure_rules.md
- core/review_core/registry/compiled_rule_registry.json

## 可选删除（不删也不会被运行时引用）
v0.1.8.x 遗留文件：
- backend/app/article_map.py
- backend/app/execution_plan.py
- core/review_core/portable/prompts/00_article_map_builder.md
- core/review_core/portable/schemas/article_map_schema.json

完整包中已不存在这些文件。

## 不需要修改
- Render 环境变量无需新增或变更。
- Gate 文件不要修改。
