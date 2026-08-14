# 审核规则

> 本文件是人工维护的 Rule Source of Truth。Registry、Gate、Agent、Feedback 均不得反向修改本文件。


## 一、终审五问

### F001｜终审只汇总既有规则

**Stage**
FINAL

**适用类型**
A / B / C / D / E

**严重级别**
BLOCKER

**判定问题**
是否仍存在上游Gate未解决的BLOCKER？

**通过条件**
不存在。

**失败条件**
任一上游BLOCKER遗留。

**例外**
- 无


## 二、严重程度分级

### F002｜严重度分级执行

**Stage**
FINAL

**适用类型**
A / B / C / D / E

**严重级别**
BLOCKER

**判定问题**
问题是否已按BLOCKER/MAJOR/MINOR正确分级？

**通过条件**
一级问题阻塞发布；二级问题优先修复；三级问题不强制。

**失败条件**
把风格小问题当致命问题，或放过事实/逻辑BLOCKER。

**例外**
- 无
