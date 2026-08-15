# Internal Test v0.1.8.0

## 结论

代码级、契约级和执行路径内测通过。**本环境没有生产 DeepSeek API 凭据，因此没有伪称完成真实模型线上回测。** CPI 修改前版本仍需部署后作为第一篇验收稿重新跑一次。

## 已通过自动测试

1. Response contracts：PASS
2. Mock review integration：PASS
3. v0.1.3 runtime regression：PASS
4. Article Map execution-plan coverage：PASS
5. Article Map exact-quote provenance guard：PASS
6. Fact candidate priority/reuse：PASS
7. MAP_AWARE plumbing：PASS
8. Markdown-only Rule source validation：PASS
9. Gate registry hash 与 v0.1.7.2 完全一致：PASS

## CPI 修改前版本：架构回测

这篇稿件此前的误判核心不是“没有 Rule”，而是全文型 Rule 没有稳定完成横向比较。新架构会把下面这些既有 Rule 放入 MAP_AWARE：

- T001 / T002
- G002
- I001 / I002 / I003 / I004 / I005 / I006
- S001 / S005 / S006 / S007
- F003

对 CPI 旧稿，Article Map 应至少能够把正文表达成以下类型的主要单元关系：

```text
T09 提出内容先行机制
→ 内容生态进一步解释机制
→ 长期主义增加成立条件
→ “内容生产型 vs 空间出租型”进行有效归纳
→ 行业痛点总结再次回扣定位/内容命题
→ 客群黄金三角增加新变量
→ “以人为主”继续解释人群/主理人机制
→ T09闭环增加案例
→ 行业痛点总结再次回扣客群命题
→ 组织放权增加组织变量
→ 复盘/困境/启示/结尾连续多轮总结
```

这张图本身不判好坏，但会迫使 S007 按其既有规则逐单元执行“删除测试/案例边际价值测试”，而不是只凭“文章有三部分、有案例、有总结”的总体印象 PASS。

同时 I005 / F003 可以直接看到全文强判断与证据链之间的关系，例如“至今没有项目能真正复制”“市面上90%”“注定南辕北辙”“任何变量缺失都会结果归零”“所有学不会的CPI，本质都是……”。是否 FAIL 仍完全由 I005/F003 当前原始条件决定。

## 重要限制

本版**没有修改 Gate**。因此它解决的是“Rule 有没有被更可靠地执行”，而不是重新定义“几个 MAJOR FAIL 才改变最终判断”。如果线上复跑时系统已经正确识别 S007/I005 等问题，但最终判定仍与编辑预期不一致，那属于下一步 Gate aggregation 校准问题，不能再用新增内容 Rule 解决。

## 上线验收建议

第一轮只跑两篇：

1. CPI 修改前版本：检查 S007 / I005 / F003 是否仍被整体印象吞掉；
2. CPI 修改后版本：检查 S007 不应因为正常归纳、必要总结而过度触发。

同时记录 Render Logs：

- `article_map elapsed`
- `direct_rules elapsed`
- `map_aware_rules elapsed`
- `fact_search elapsed`
- `review complete elapsed`

用同一篇文章与 v0.1.7.2 的耗时比较，才能判断真实生产模型下的速度收益/成本。
