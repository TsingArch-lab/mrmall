# Fact Search v0.1.7.0

## Flow

Article → Fact Claim Extractor → Tavily Search (concurrent) → Fact Verifier → Verification Results → Existing Rules → Gate

## Boundary

- 只核验客观事实与明确外部归属观点。
- 不为作者判断主动寻找支持材料。
- `no_reliable_source` 不等于事实错误。
- 搜索失败或未配置 Key 时自动降级为 `NOT_RUN`。
- 搜索层不直接决定 PASS / REVISE / STOP。

## Render env

```
FACT_SEARCH_PROVIDER=tavily
FACT_SEARCH_API_KEY=...
```

Optional:
```
FACT_SEARCH_MAX_CLAIMS=8
FACT_SEARCH_MAX_RESULTS=5
FACT_SEARCH_CONCURRENCY=4
FACT_SEARCH_DEPTH=basic
FACT_SEARCH_TIMEOUT_SECONDS=20
FACT_VERIFIER_TIMEOUT_SECONDS=60
```
