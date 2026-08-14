# 可移植性检查清单

一个新大模型平台满足以下任意最低条件，即可接入：

- [ ] 能接收至少数万字文本，或支持分批执行
- [ ] 能遵循“只评 supplied Rule IDs”
- [ ] 能输出可解析 JSON（原生或 Prompt 约束）
- [ ] 能引用文章原文作为 evidence

增强能力：
- [ ] 原生 JSON Schema / structured output
- [ ] 低 temperature / deterministic 参数
- [ ] 文件上传
- [ ] Web Search / 浏览器
- [ ] API

没有增强能力不影响核心架构，只影响自动化程度。
