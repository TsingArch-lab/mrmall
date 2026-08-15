# Patch Instructions — v0.1.8.0 → v0.1.8.1

## 适用前提
仅适用于当前线上代码已经是 **v0.1.8.0**。

## GitHub 需要覆盖的运行文件
按原路径覆盖：

```text
VERSION
backend/app/article_map.py
backend/app/config.py
backend/app/main.py
core/review_core/engine/review_runtime.yaml
core/review_core/portable/prompts/00_article_map_builder.md
core/review_core/portable/prompts/01_rule_batch_evaluator.md
core/review_core/portable/schemas/article_map_schema.json
frontend/app.js
```

`ARCHITECTURE_v0.1.8.1.md`、`INTERNAL_TEST_v0.1.8.1.md`、`RUNTIME_CHANGELOG_v0.1.8.1.md` 与 `scripts/` 为说明/测试文件，不影响线上运行，可一并提交，也可不提交。

## 不需要操作
- 不需要替换 `rules/`。
- 不需要替换 `gates/`。
- 不需要修改 `gate_registry.json`。
- 不需要新增或修改 Render 环境变量。
- Tavily / DeepSeek 环境变量保持原样。

## 部署后验收
1. `/health` 与页面右上角应显示 `0.1.8.1`。
2. 先关闭联网核验，用 CPI 修改前版本跑一次。
3. 日志重点查看：
   - `article_map done ... units=...`：应显著高于 v0.1.8.0 的 8 个，接近真实论证块数量；
   - `map_aware_rules ... failed=...`；
   - S007 / I005 / F003 的状态与 evidence。
4. 再跑 CPI 修改后版本，确认有效归纳、必要转场、承担不同论证功能的案例不会被机械误伤。

## 回滚
若生产回归异常，直接恢复 v0.1.8.0 上述同路径文件即可；Rules/Gate 本版未变化。
