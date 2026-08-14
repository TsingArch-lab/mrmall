# Rule-first 批量评估合同 v0.4.0

## 目标

让模型只做一件事：**判断既有 Rule 是否被当前文章触发。**

模型不是自由审稿人，也不是规则设计者。

## 强制执行顺序

1. Runtime 确定 `content_type`。
2. 程序从 Gate + Registry 编译 `applicable_rule_ids`。
3. 一次性把适用规则批量交给 `RULE_BATCH_EVALUATOR`。
4. Evaluator 只输出 PASS / FAIL / NA / UNRESOLVED。
5. 程序按 `gates/*.yaml` 做确定性 Gate 聚合。
6. Feedback Composer 只接收 FAIL Rules，不接收“自由审稿意见”。
7. `provenance_validator.py` 校验所有负面反馈。
8. 校验不通过的反馈直接 DROP；必要时只针对该项运行 Adjudicator。

## Rule Evaluator 禁止输出

- overall critique
- improvement advice
- suggested titles
- suggested structure
- candidate rules
- “通常好文章应该……”
- 任何 Registry 中不存在的质量标准

## PASS 的低成本输出

PASS 只返回 Rule ID，不返回理由。

## FAIL 的允许输出

每条 FAIL 只能返回：
- `rule_id`
- `article_evidence`
- `match_explanation`

`match_explanation` 只能解释：

> 原文证据如何命中该 Rule 已有的 `fail_condition`。

它不得评价任何超出 `fail_condition` 的问题。

## UNRESOLVED

当模型无法可靠判断 PASS/FAIL 时，输出 `UNRESOLVED`。

UNRESOLVED：
- 不是 FAIL；
- 不得阻塞 Gate；
- 只触发局部二次裁决；
- 不得进入作者端负面反馈。

## 反馈生成

作者端负面反馈的合法数据源只有：

```text
failed_rules[]
```

不是：

```text
article + model editorial intuition
```

核心诊断和问题归并仍可使用自然语言，但每条必须携带 `supporting_rule_ids` 和 `article_evidence`，并通过确定性 provenance validator。

## 算力原则

完整稿件审核默认：
- 0次逐Rule调用；
- 1次批量Rule评估；
- 1次FAIL-only反馈组织；
- 只有冲突项才局部复审。

因此 Rule-first 不等于 Rule-per-call。
