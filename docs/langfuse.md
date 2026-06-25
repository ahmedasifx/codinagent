# Langfuse Observability

Tracing, cost, and scoring for every agent run. All of it is **optional** — when
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are unset, the app runs unchanged with no
tracing.

## Setup

1. Set in `backend/.env` (works with a self-hosted instance too):
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=http://host.docker.internal:3000   # or your host
   ```
   (`LANGFUSE_HOST` is also accepted.) From a container, use
   `host.docker.internal`, not `localhost` — the compose backend already maps it via
   `extra_hosts: host.docker.internal:host-gateway`.

2. **Seed model prices** so cost is computed (one-off; re-run after changing models):
   ```
   python backend/scripts/seed_langfuse_models.py
   ```
   This pulls live per-token prices from OpenRouter's `/models` API and registers a
   matching custom model in Langfuse for each slug the app uses (primary + fallbacks +
   per-agent overrides). Without it, OpenRouter slugs aren't in Langfuse's price table
   and cost shows $0.

## What's captured automatically

- **Traces**: each run is `start_trace()`-d with a known id, tagged by agent slug and
  grouped by `session_id`. The full `select → agent → tools` tree, inputs/outputs.
- **Token usage + cost**: `get_llm()` sets `stream_usage=True`, so streamed responses
  carry token counts; cost = usage × seeded price.

## Scores

### User feedback (👍/👎)
Wired end-to-end: the runner emits a `trace` SSE event with the run's `trace_id`; the
chat UI stores it and shows thumbs under each answer; clicking posts to `POST /feedback`
→ `langfuse.score(name="user_feedback", value=1|0)` on that trace.

### LLM-as-judge (online evaluation) — configured in the Langfuse UI, no code
1. In Langfuse: **Evaluations → LLM-as-judge → + New evaluator**.
2. Add an eval model + API key. OpenRouter works as an OpenAI-compatible provider
   (base URL `https://openrouter.ai/api/v1`, your OpenRouter key, an instruct model).
3. Pick/author a template (relevance, helpfulness, hallucination, correctness…).
4. Map the template variables to the trace's `input` / `output`.
5. Scope it to **new traces**. Scores then appear on each run within ~a minute.

## Code map

| Concern | Location |
|---|---|
| Client, `start_trace()`, `score()`, `flush()` | `backend/app/core/observability.py` |
| Trace creation + `trace` SSE event | `backend/app/engine/runner.py` |
| `stream_usage=True` | `backend/app/engine/llm.py` |
| `POST /feedback` | `backend/app/api/chat.py` |
| Price seeder | `backend/scripts/seed_langfuse_models.py` |
| Thumbs UI | `frontend/src/components/MessageBubble.tsx`, `hooks/useAgent.ts` |
