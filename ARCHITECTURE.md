# Architecture｜Web v0.1.2

```text
Browser
  ↓
Vercel static frontend
  ↓
Render FastAPI
  ↓
Request contract
  ↓
Provider adapter (OpenAI-compatible / mock)
  ↓
Response normalization + contract validation
  ↓
Router (AUTO only)
  ↓
Rule Batch Evaluator
  ↓
Deterministic Gate
  ↓
Feedback Composer
      ↘ contract failure → deterministic FAIL-only fallback
  ↓
Provenance-safe response
```

内容标准仍只有一条合法来源：

```text
Markdown Rules
→ Compiler
→ Registry
→ Runtime
```

v0.1.2 新增的“模型响应归一化/修复”属于协议兼容层，不得改变 Rule 语义。
