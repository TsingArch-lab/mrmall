# v0.1.5 — “值得保留” Positive Evidence Layer

## 目标
让“值得保留”从“没有触发问题”变成有证据、有 Rule 来源的正向反馈，同时不允许模型自由表扬或新增审稿标准。

## 治理原则
- No PASS Rule, No Strength。
- 每条 Strength 必须绑定已 PASS 且允许生成正向反馈的 Rule ID。
- 每条 Strength 必须引用文章原文证据，后端校验该证据确实存在于文章。
- FAIL / NA / UNRESOLVED Rule 不得生成 Strength。
- Strength 不参与 Gate、严重度、最终判断。
- 不把“没有犯错”当优点。

## 架构
Rule Evaluator → PASS Rule IDs → Strength Eligible Filter → Strength Extractor → Positive Provenance Validator → 作者端“值得保留”

负面链路保持独立：
FAIL Rules → Gate/Clustering → Feedback Composer

## Strength Eligible Rules
主要覆盖：
- 选题价值与经营决策落点
- A/B/C/D/E 对应的有效证据结构
- 具体机制、高级观点、非事实改写
- 结构闭环、有效开头、小标题关系、正文立住
- 具体表达兑现

主动排除：
- G001/G002 等外部真实性/事实边界 Rule
- E003/I003/I005/I006/S004 等条件型或“未犯错”型 Rule
- F001/F002/F003 Gate/终审规则
- X004/X005/X006 等主要用于识别表达风险的 Rule

## 预期
- 龙湖海口天街：能提取“具体经营决策过程”“机制与证据对应”等强项。
- 吾悦存量改造：即便最终“需要修改”，仍能保留武进/海口案例中的具体决策过程与差异化机制。
- 清单式差稿：即使部分 Rule PASS，也不得生成“信息很多”式空泛表扬。
