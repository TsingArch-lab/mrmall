# 规则治理协议 v0.3e

## 核心原则

**Rules 是内容质量判断的唯一事实源（Single Source of Truth）。**

Registry、Gate、Agent、Feedback 均无权创造新的内容标准。

---

## 权限边界

### Rules
可以定义：
- 什么是好内容；
- 什么构成问题；
- 哪些规则适用于哪些内容类型；
- 例外条件。

### Registry
只可以：
- 翻译 Rules；
- 结构化 Rules；
- 标记 applicability / severity / evaluation。

不得扩展原意。

### Gate
只可以：
- 引用 Rule ID；
- 聚合 Rule 结果；
- 决定 PASS / REVISE / STOP。

不得新增质量条件。

### Agent
只可以：
- 执行 Rules；
- 提取证据；
- 解释 Rule 触发原因；
- 组织反馈。

不得补充模型自己的编辑标准。

### Feedback
只可以：
- 展示 Rules 已识别的问题；
- 对同源问题进行语义归并；
- 标识已成立内容。

不得产生新的质量判断。

---

## 新标准治理流程

```text
Observed Problem
    ↓
Candidate Rule
    ↓
Human Review
    ↓
Original Rule File
    ↓
Registry Compilation
    ↓
Gate Reference
    ↓
Agent Execution
```

任何跳过 `Human Review → Original Rule File` 的新增标准均视为系统违规。

---

## 三条硬约束

1. **No Rule, No Feedback**
2. **No Rule, No Block**
3. **Candidate Rule has zero enforcement power**



## v0.4.0 执行补充：Rule-first, Fail-closed

- 正式审核必须先得到 Rule evaluation，再生成反馈。
- 禁止“先自由审稿，再为结论寻找 Rule”。
- 作者端负面反馈必须通过确定性 provenance validator。
- provenance 校验失败时默认 DROP，而非由模型自行解释补救。
- UNRESOLVED 是运行状态，不是质量失败；只允许局部复审。
- Gate aggregation 必须程序化执行，不交给模型。

## v0.4.1｜Markdown Rules 唯一源

`rules/*.md` 是唯一人工维护的内容判断源。Registry 是 build artifact，可删除后重新生成。

合法链路：

`Markdown Rules → Compiler → Registry → Rule-first Runtime → Gate → Feedback`

禁止 Registry、Gate、Agent、Feedback 反向产生或修改 Rule。删除 MD 中的 Rule ID 后，该 Rule 在下一次编译中必须消失。
