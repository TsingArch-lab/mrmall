# Review Core v0.5.0-portable

## 定位

这不是“某个大模型的审稿 Prompt”，而是一套模型无关的内容质量执行系统。

## 六层架构

```text
[1] Markdown Rules — 人工唯一事实源
        ↓ compile
[2] Compiled Registry — 机器可读规则
        ↓ applicability
[3] Rule Batch Evaluator — 唯一需要大模型推理的核心层
        ↓ FAIL/PASS/NA/UNRESOLVED
[4] Deterministic Gate Runtime — 程序聚合，不交给模型
        ↓
[5] Feedback Composer — 只消费 FAIL Rules
        ↓
[6] Provenance Validator — 程序反向校验 No Rule, No Feedback
```

事实核验是旁路插件：

```text
Search / Source Verification → verification_results → Rule Evaluator
```

它查事实，不创造规则。

## 不随模型变化的部分
- Markdown Rules
- Rule IDs
- Registry Schema
- Gate thresholds
- Dimension mapping
- Provenance validator
- Author feedback format
- Search scope

## 随模型变化的部分
只有：
- Rule判断准确率
- UNRESOLVED比例
- 同源问题语言归并质量

因此升级或更换模型不需要重写内容方法论。

## 核心治理约束

**No Rule, No Feedback.**
**No Rule, No Block.**
**Rules are authored only in Markdown.**
**Gate decisions are deterministic.**
**LLM is an executor, not a legislator.**
