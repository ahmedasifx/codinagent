# CLAUDE.md

A full-stack **coding agent**: a chat UI that asks an LLM to write and execute code inside a sandboxed cloud environment, streaming tokens, tool calls, and live app previews back to the browser.

## Stack

- **Backend** (`backend/`) — FastAPI + LangGraph ReAct agent. LLM access via **OpenRouter** (OpenAI-compatible API), code execution via **E2B** cloud sandbox. Streams to the client over SSE.
- **Frontend** (`frontend/`) — React 18 + TypeScript + Vite. Plain `fetch` SSE client (no extra deps beyond React).

## Layout

```
backend/
  agent.py        # LangGraph graph, E2B-backed tools, system/workflow prompts, streaming runner
  main.py         # FastAPI app: POST /chat/stream (SSE), DELETE /sandbox, GET /health
frontend/src/
  hooks/useAgent.ts          # SSE parsing + message/preview/workflow state (core client logic)
  components/MessageBubble.tsx
  components/ToolCallPanel.tsx  # collapsible tool I/O; renders base64 PNG charts inline
  components/PreviewPanel.tsx   # iframe for the sandbox preview URL
  types/index.ts             # ChatMessage + AgentEvent union (must mirror backend event dicts)
docker-compose.yml  # backend:8000, frontend:3000 (CORS-allowed)
analysis/langfuse/  # vendored external clone (Langfuse) for reference only — NOT part of this project; ignore it
```

## How it works

1. `main.py` `POST /chat/stream` receives `{message, history}` and returns an `EventSourceResponse` driven by `run_agent_stream()`.
2. `agent.py` graph: `route → agent → tools → agent` (loop until no tool calls).
   - **route**: a separate non-streaming LLM call classifies the request as `landing_page` / `fullstack` / `general`; its tokens are filtered out of the stream (only `langgraph_node == "agent"` tokens reach the user).
   - **agent**: `SYSTEM_PROMPT` + a workflow-specific addendum (`WORKFLOW_PROMPTS`), bound to `TOOLS`.
   - **tools**: executed against a module-level singleton E2B `Sandbox`.
3. `run_agent_stream()` consumes `GRAPH.astream_events(version="v2")` and yields typed dicts.

### SSE event protocol (keep `backend` and `frontend/src/types/index.ts` in sync)

| `type` | fields | meaning |
|--------|--------|---------|
| `token` | `content` | LLM token chunk (agent node only) |
| `trace` | `trace_id` | Langfuse trace id for this run (enables feedback scoring) |
| `workflow` | `workflow` | classified workflow (session-level) |
| `tool_call` | `name`, `args` | tool started |
| `tool_result` | `content` | tool output |
| `preview` | `url` | live sandbox app URL (parsed from `PREVIEW_URL:` in a tool result) |
| `done` | — | turn complete |
| `error` | `content` | runtime error |

### Tools (`agent.py`, all `@tool`-decorated, collected in `TOOLS`)

`execute_python`, `install_package`, `run_command`, `write_file`, `read_file`, `list_files`, `start_server`, `stop_server`. The agent builds projects under `/home/user/app`.

## Sandbox model — important constraints

- **Single module-level sandbox singleton** (`_sandbox` in `agent.py`). Fine for one local user; multi-user would need per-session sandboxes keyed by a session id.
- Sandbox state (filesystem + Python kernel variables) **persists across calls within a session**. `DELETE /sandbox` (and the frontend "Reset" button) kills it to start fresh.
- `start_server` runs dev servers in the background (`_background_processes` keyed by port), polls until the port answers, bumps the sandbox timeout to 3600s, and returns a public `PREVIEW_URL`.
- Servers **must bind to `0.0.0.0`** (Vite needs `--host` and `server: { host: true, allowedHosts: true }`) to be reachable through the E2B proxy.

## Running

Backend:
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill E2B_API_KEY and OPENROUTER_API_KEY
uvicorn main:app --reload --port 8000
```

Frontend:
```bash
cd frontend && npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev            # http://localhost:5173
npm run build          # tsc + vite build (type-checks)
```

Or: `docker compose up --build` (frontend on :3000, backend on :8000).

## Environment

- `backend/.env` — `E2B_API_KEY`, `OPENROUTER_API_KEY`, optional `OPENROUTER_MODEL` (default `deepseek/deepseek-coder`; any OpenRouter slug works, e.g. `anthropic/claude-sonnet-4-5`).
- `frontend/.env` — `VITE_API_URL` (baked in at build time).
- `.env*` files are gitignored — never commit secrets.

## Conventions / gotchas

- CORS allowlist in `main.py` is hardcoded to `http://localhost:5173` and `:3000`; add new origins there.
- When changing the event protocol, update **both** the backend yield dicts and the `AgentEvent` union in `frontend/src/types/index.ts`, plus the handler switch in `useAgent.ts`.
- The router makes an extra LLM call per turn — its tokens are intentionally suppressed; preserve the `langgraph_node == "agent"` guard if you touch streaming.
- No test suite or linter is configured; `npm run build` (tsc) is the only type/build check.
