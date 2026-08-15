# Mall Content OS Web v0.1.7.2

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


## v0.1.6.2 Runtime Performance

见 `RUNTIME_PERFORMANCE_v0.1.6.2.md`。本版本不修改 Rules 或 Gate。


## v0.1.7.2

- 事实核验表格移动到“值得保留”之后。
- Fact Search 与主 Rule Evaluator 并行。
- 搜索上限仍为 8 条。
- Rules / Gate 不变。

## v0.1.7.0

- 新增 `S007｜论证推进与功能增量`（MAJOR），用于识别同义重复、同质案例重复证明、未兑现铺垫与偏航式新增；允许有效归纳、必要转场与同主题持续深入。
- 新增可选事实搜索：前端勾选“联网核验关键事实”后，后台先识别高风险客观事实，再通过 Tavily 搜索并生成核验结果；搜索结果只作为现有 Rules 的证据输入，不创造新标准。
- 搜索失败自动降级为 NOT_RUN，不会因为“搜不到”直接判文章事实错误。

Render 需要新增：
```
FACT_SEARCH_PROVIDER=tavily
FACT_SEARCH_API_KEY=<你的 Tavily API Key>
```
