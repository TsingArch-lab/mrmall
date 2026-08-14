# Mall Content OS v0.4.0

本版本为执行架构升级，不新增内容质量标准。

核心变化：
- Rule-first 批量评估；
- 完整稿件默认 2 次 LLM 调用（Rule Batch + FAIL-only Feedback）；
- Gate 聚合改为确定性执行；
- 新增 UNRESOLVED 局部裁决机制；
- 新增 compiled registry + semantic hash；
- 新增 deterministic provenance validator；
- 正式负面反馈只能来自当前 FAIL Rules。

核心原则：**模型执行标准，不创造标准。**

## v0.4.1｜直接替换 Rules

以后只需要替换或编辑 `rules/*.md`，然后执行：

```bash
python engine/compile_rules.py
python engine/validate_rule_source.py
```

无需手工同步 Registry、Gate、Agent。
