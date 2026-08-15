# Patch Instructions｜v0.1.7.2 → v0.1.8.0

本 Patch **只能用于当前线上代码已是 v0.1.7.2** 的情况。

## 必须覆盖/新增的运行文件

### Render / Backend

```text
backend/app/article_map.py                         NEW
backend/app/execution_plan.py                      NEW
backend/app/config.py                              REPLACE
backend/app/fact_search.py                         REPLACE
backend/app/llm.py                                 REPLACE
backend/app/main.py                                REPLACE
backend/app/review_core.py                         REPLACE
core/review_core/portable/prompts/00_article_map_builder.md   NEW
core/review_core/portable/prompts/01_rule_batch_evaluator.md  REPLACE
core/review_core/portable/prompts/05_strength_extractor.md    REPLACE
core/review_core/portable/schemas/article_map_schema.json     NEW
core/review_core/engine/review_runtime.yaml                   REPLACE
VERSION                                           REPLACE
```

### Vercel / Frontend

```text
frontend/app.js                                   REPLACE
```

`frontend/app.js` 本次只负责把页面版本显示更新为 `Web 0.1.8.0`；页面布局没有改动。

## 可选同步文件

以下文件用于文档和回归测试，不影响生产运行：

```text
ARCHITECTURE.md
backend/.env.example
RUNTIME_CHANGELOG_v0.1.8.0.md
INTERNAL_TEST_v0.1.8.0.md
TEST_STATUS_v0.1.8.0.md
scripts/test_article_map_architecture.py
scripts/test_map_aware_plumbing.py
```

## 明确不要改

```text
core/review_core/rules/*
core/review_core/gates/*
core/review_core/portable/runtime/gate_registry.json
core/review_core/registry/compiled_rule_registry.json
```

这些文件在 v0.1.8.0 与 v0.1.7.2 保持原逻辑；Rules 仍为 49 条，semantic hash 不变。

## Render 环境变量

无需新增任何变量即可运行，默认值：

```text
ARTICLE_MAP_TIMEOUT_SECONDS=70
ARTICLE_MAP_MAX_UNITS=18
```

只有以后需要调优时才需要在 Render Environment 中显式设置。

## 部署后检查

1. Render `/health` 应显示 `version: 0.1.8.0`。
2. Registry hash 应仍为 `sha256:31f357cf5a64d476ca35c9d86287c18a870bac33d9ddd3efafc8ab507dfce2df`。
3. 网页右上角应显示 `Web 0.1.8.0`。
4. 用 CPI 修改前版本重新跑一次，并保存 Render Logs。重点观察：
   - `article_map done`
   - `execution_plan`
   - `direct_rules done`
   - `map_aware_rules done`
   - `fact_search done`（若开启联网）
   - `review complete`
