# Runtime / UI Changelog v0.1.7.1

- Facts UI moved after Strengths.
- Facts UI changed from stacked cards to a table.
- `FACT_SEARCH_MAX_CLAIMS` remains unchanged at 8.
- Main Rule Evaluator and Fact Search now run concurrently.
- Main evaluator uses the existing NOT_RUN safety guard while web search is in flight.
- Only existing fact-sensitive Rules G001/G002 receive a targeted recheck when search returns a material adverse signal (`contradicted`, or `high + questionable`).
- No content Rule changes.
- No Gate changes.
