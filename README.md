# Mall Content OS Web v0.1.4

本版为 **Argumentation Calibration**。

审核标准从“证明式”调整为“解释式”：商业文章必须有事实→推导→判断，但不要求像学术论文一样为每个判断配置第三方验证、失败案例和排他因果证明。

同时强化对真正低质量内容的拦截：
- 成绩/品牌/活动清单式堆砌；
- 企业自我评价直接当能力证明；
- 事实后只贴“专业/成功/体系能力”等标签；
- 没有解释为什么、没有决策过程、没有机制。

详见 `RULE_CHANGELOG_v0.1.4.md`。

## v0.1.5 Positive Evidence Layer
“值得保留”由独立 Strength Extractor 生成：只使用已 PASS 的 strength-eligible Rules，并要求逐条绑定原文证据。正向反馈与 Gate/负面反馈完全解耦。
