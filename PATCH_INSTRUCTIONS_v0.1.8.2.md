# Patch Instructions: v0.1.8.1 → v0.1.8.2

只需覆盖 Patch 包内文件到 GitHub 相同路径，然后等待 Render / Vercel 自动部署。

## Backend/runtime
- `backend/app/execution_plan.py`
- `backend/app/review_core.py`
- `backend/app/config.py`
- `backend/app/llm.py`
- `core/review_core/portable/prompts/01_rule_batch_evaluator.md`
- `backend/app/main.py`

## Frontend version marker
- `frontend/app.js`

## Tests / docs（不影响生产运行，但建议一并提交）
- `scripts/test_rule_test_batches.py`
- `scripts/test_rule_test_trace_contract.py`
- `RUNTIME_CHANGELOG_v0.1.8.2.md`
- `INTERNAL_TEST_v0.1.8.2.md`
- `PATCH_INSTRUCTIONS_v0.1.8.2.md`
- `VERSION`

## Environment
无需新增环境变量。可选参数已有默认值：
- `RULE_TEST_BATCH_TIMEOUT_SECONDS=180`
- `RULE_TEST_TRACE_MAX_CHARS=6000`

## 部署后重点看日志
应出现类似：
```text
[review] map_aware_rule_tests start batches=3 ...
[rule-test] batch start name=ARGUMENT_PROGRESSION ...
[rule-test] trace=...
[rule-test] batch done name=ARGUMENT_PROGRESSION ... failed=[...]
[rule-test] batch done name=MECHANISM_DERIVATION ...
[rule-test] batch done name=CLAIM_EVIDENCE_STRENGTH ...
[review] map_aware_rule_tests done ...
```
