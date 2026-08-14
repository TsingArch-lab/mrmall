# Web v0.1 Architecture

```text
Browser / Vercel Static Frontend
        ↓ HTTPS
FastAPI / Render
        ↓
Review Orchestrator
  ├─ Content Type Router (optional LLM call)
  ├─ Applicable Rule Compiler (deterministic)
  ├─ Rule Batch Evaluator (LLM)
  ├─ Gate Aggregator (deterministic)
  ├─ Feedback Composer (FAIL-only LLM)
  └─ Provenance Validation (deterministic)
        ↓
LLM Provider Adapter
```

## Invariants

- Markdown Rules are the human source of truth.
- LLM cannot create new quality criteria.
- No Rule, No Feedback.
- Gate decisions are deterministic.
- API keys live on backend only.
- Provider-specific API details stay inside the Adapter layer.
