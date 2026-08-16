# Mall Content OS v0.1.10.0 — Rule / Dimension 分层补丁

适用基线：已部署 v0.1.9.0，并已应用「恢复 DeepSeek 默认 thinking + 延长 timeout」及上一版 FAIL-FIRST patch 的当前线上版本。

## 这版解决什么
此前一个 Rule FAIL 会被程序直接映射成对应五维“有明显问题”。这会导致两个相反风险：
- 为避免局部问题拖低全文，Rule Evaluator 倾向过度 PASS；
- 一旦 Rule 判严，局部小问题又会直接污染全文维度。

v0.1.10.0 将三层职责拆开：
1. Rule Evaluator：只判断具体 Rule 是否被违反；
2. Dimension Assessor：只判断已验证 FAIL 是否足以影响整个五维之一；
3. Gate：继续按原有确定性规则决定“可以继续 / 需要修改”。

## 文件替换
将补丁内文件覆盖到仓库同路径：

- `backend/app/review_core.py`
- `core/review_core/portable/prompts/01_rule_batch_evaluator.md`
- `core/review_core/portable/prompts/02_feedback_composer.md`

然后提交 GitHub，等待 Render 自动部署。

## 核心行为变化
- Rule FAIL 不再在 `aggregate()` 中自动把五维改成“有明显问题”。
- Rule Evaluator 使用非抵消式 FAIL-FIRST：完整命中 fail_condition 且无 exception 即 FAIL；其他优点不能抵消。
- 同时防止过严：局部症状/轻微瑕疵不等于完整命中 fail_condition。
- 五维由现有 Feedback Composer 同一次 secondary-model 调用顺带做 impact aggregation，不增加新的 API 调用。
- 没有对应 FAIL Rule 的维度绝不能被降级。
- 有 FAIL 的维度仍可保持“达标”，如果问题只是局部/孤立/有限范围。
- 本版暂不实现“突出”；只解决 FAIL 与五维影响程度的分层。
- Gate、Rules、Registry、Schema、Fact Search、Strength Extractor 均不改。

## 建议回测顺序
1. 《项目总岗位十年变迁》：预期应出现至少一个真实 Rule FAIL；但局部表达类 FAIL 不应自动拖低整个表达维度。
2. CPI 修改前：预期结构/推进相关 FAIL 应被识别。
3. CPI 修改后：检查是否出现过度 FAIL。
4. 已确认优秀稿：检查 FAIL-first 是否造成误杀。

重点记录：
- `evaluate_rules elapsed`
- `failed_ids`
- `final`
- 新日志：`[review] dimension_impact states=...`
