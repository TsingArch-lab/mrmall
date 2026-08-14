# Mall Content OS 架构 v0.4.0

## 1. Source of Truth

`Rules` 是内容质量判断的唯一事实源。

```text
Rules → Registry → Runtime → Gate → Feedback
```

后四层只能执行和翻译，不能增加质量标准。

## 2. Registry

Registry 是 Rules 的机器翻译层。

v0.4.0 新增 `compiled_rule_registry.json`：
- 聚合全部 Registry 规则；
- 保留 source_file / source_section；
- 为每条规则生成 `semantic_hash`；
- 增加 execution-only 元数据；
- execution 元数据不得改变规则语义。

语义 hash 用于防止运行时规则漂移。

## 3. 两种执行模式

### FULL_ARTICLE_REVIEW

用于完整稿件审核/回测。

默认只需要：
1. 一次批量 Rule evaluation；
2. 一次 FAIL-only feedback composition。

如果 content_type 已由 UI/用户指定，则不需要额外 Router 模型调用。

只有 UNRESOLVED 或 provenance 冲突项进入局部二次裁决。

### CREATION_STAGE

用于选题→证据→观点→结构→成稿的生产过程。

仍按 Gate 分阶段运行，但**一个 Gate 内所有 Rule 一次批量判断**，禁止一条 Rule 一次模型调用。

## 4. Rule Batch Evaluator

模型仅负责：
- PASS
- FAIL
- NA
- UNRESOLVED

不负责：
- Gate 聚合
- 总体评价
- 修改建议
- 新规则

PASS 只输出 ID；FAIL 才输出证据与匹配解释，从而降低 token 消耗。

## 5. Gate Aggregator

Gate 是纯确定性状态机。

输入：
- FAIL Rule IDs
- Rule severity
- gates/*.yaml 聚合条件

输出：
- PASS / REVISE / STOP

不得使用大模型“整体感觉”覆盖结果。

## 6. Feedback Composer

负面反馈输入只能是 `failed_rules[]`。

它可以：
- 合并同源问题；
- 把机器语言转成人类语言。

它不能：
- 重新阅读全文后自由找问题；
- 扩大规则语义。

## 7. Provenance Validator

`engine/provenance_validator.py` 在输出前执行确定性检查：
- Rule ID 是否存在；
- 是否当前真实 FAIL；
- 是否有文章证据；
- 无 FAIL 时是否出现负面反馈。

不通过即 DROP。

## 8. 事实核验

Search 只负责查清客观事实和明确外部归属观点。

```text
Search 查事实
Rules 判断是否构成质量问题
Gate 决定能否继续
```

Search 不为作者观点寻找支持材料。

## 9. Candidate Rule

```text
Observed Problem → Candidate Rule → Human Review → Rules → Registry → Runtime
```

Human Review 之前 enforcement = 0。

## 10. 算力设计

v0.4.0 的优化目标不是“少判断规则”，而是“少调用模型”。

主要控制手段：
- Rule applicability 程序化筛选；
- 同阶段/整稿规则批处理；
- Compact Registry；
- PASS ID-only；
- Feedback 只读取 FAIL；
- 局部 Adjudication；
- Registry hash 缓存；
- 已知内容类型跳过 Router。

因此 Rule-first 不应退化成 Rule-per-call。

## v0.4.1｜MD-first Rules

Rules 保持 Markdown，供主编直接替换。运行时不直接执行 Markdown，而是在审核前编译成 Registry。

- Authoring: `rules/*.md`
- Build: `engine/compile_rules.py`
- Runtime registry: `registry/compiled_rule_registry.json`
- Integrity check: `engine/validate_rule_source.py`

Registry 永远不是 Rule 的反向来源。
