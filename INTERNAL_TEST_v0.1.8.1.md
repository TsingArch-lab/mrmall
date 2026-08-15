# Internal Test v0.1.8.1

本地环境没有生产 DeepSeek API Key，因此本次测试分为“确定性架构回归”和“线上待验收”两部分。

## 已完成的确定性测试
- Argument Blocks 不因语义相似而合并。
- 标题只作为下一 prose block 的元数据，不吞掉相邻正文。
- LLM 即使漏标某些 Block，normalizer 仍保持 source block count 与 map unit count 一致。
- hallucinated anchor quote 不可进入 Map evidence；自动回退到该 source block 的真实 excerpt。
- DIRECT_TEXT / MAP_AWARE Rule 覆盖仍严格等于 applicable Rule 集合，且无交集。
- Fact Search 候选优先级保持不变。
- Rules 与 Gate 做 byte-level 对比，均保持 v0.1.8.0 不变。

## CPI 回归验收标准（部署后）
必须用同一生产模型分别跑：
1. CPI 修改前版本：预期不应再出现 33 条 applicable Rules 全 PASS；重点观察 S007、I005、F003 的实际状态和 evidence。
2. CPI 修改后版本：不能因为更严格的 Map 粒度而机械判重复；有效归纳、必要转场、承担不同功能的案例应继续被识别。

只有“旧稿能抓到真实问题 + 新稿不被机械误伤”同时成立，Argument Map 才算通过编辑回归。
