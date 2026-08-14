# Mall Content OS Web v0.1.3

Review Correctness Patch。没有新增或修改任何内容质量 Rule。

- 未核验 ≠ 事实错误：NOT_RUN 时，仅因“无法核实/缺来源”产生的 G001/G002 FAIL 转为 UNRESOLVED。
- 后台 Rule 粒度 ≠ 作者端问题数量：同源 FAIL 预聚类；F001/F002 等 Gate 后果不单独形成作者问题。
- Markdown Rules、severity、Gate 阈值均未改变。
