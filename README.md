# Coding Agent

A full-stack coding agent using **E2B** (sandboxed code execution), **LangGraph** (ReAct agent), **OpenRouter** (LLM access), **FastAPI** (streaming SSE backend), and **React** (frontend).

```
coding-agent/
├── backend/
│   ├── agent.py          # LangGraph ReAct graph + E2B tools
│   ├── main.py           # FastAPI SSE server
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── App.css
    │   ├── hooks/useAgent.ts
    │   ├── components/
    │   │   ├── MessageBubble.tsx
    │   │   └── ToolCallPanel.tsx
    │   └── types/index.ts
    ├── index.html
    ├── package.json
    └── .env.example
```

---

## Setup

### 1. Get API keys

| Key | Where |
|-----|-------|
| `E2B_API_KEY` | [e2b.dev](https://e2b.dev/auth/sign-up) |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai/keys) |

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# → fill in E2B_API_KEY and OPENROUTER_API_KEY in .env
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# → open http://localhost:5173
```

---

## Architecture

```
User prompt
    │
    ▼
React UI (SSE client)
    │  POST /chat/stream
    ▼
FastAPI (EventSourceResponse)
    │
    ▼
LangGraph ReAct Agent
  ├── ChatOpenAI → OpenRouter → deepseek/deepseek-coder (or any model)
  └── Tools
       ├── execute_python   → E2B Sandbox (Jupyter kernel)
       ├── install_package  → pip inside sandbox
       ├── write_file       → sandbox filesystem
       └── read_file        → sandbox filesystem
```

### Streaming event protocol

The backend emits newline-delimited SSE events. Each `data:` line is a JSON object:

| `type`        | Fields           | Meaning                     |
|---------------|------------------|-----------------------------|
| `token`       | `content`        | LLM token chunk             |
| `tool_call`   | `name`, `args`   | Tool invocation started     |
| `tool_result` | `content`        | Tool execution result       |
| `done`        |                  | Turn complete               |
| `error`       | `content`        | Runtime error               |

### Changing the model

Edit `OPENROUTER_MODEL` in `backend/.env`. Any OpenRouter model slug works:

```
deepseek/deepseek-coder          # default — great for code, cheap
anthropic/claude-sonnet-4-5      # stronger reasoning
openai/gpt-4o                    # OpenAI flagship
meta-llama/llama-3.1-70b-instruct
```

---

## Key files

### `backend/agent.py`
- **`get_llm()`** — builds a `ChatOpenAI` client pointed at `https://openrouter.ai/api/v1`
- **`execute_python` / `install_package` / `write_file` / `read_file`** — LangChain `@tool` functions that wrap the E2B `Sandbox`
- **`build_graph()`** — LangGraph `StateGraph` with `agent → tools → agent` loop
- **`run_agent_stream()`** — async generator over `astream_events` that yields typed event dicts

### `backend/main.py`
- `POST /chat/stream` — accepts `{message, history}`, returns SSE stream
- `DELETE /sandbox` — kills the E2B sandbox (useful for resetting state)

### `frontend/src/hooks/useAgent.ts`
- Manages message state, reads SSE chunks, dispatches token/tool events onto the correct message

### `frontend/src/components/ToolCallPanel.tsx`
- Collapsible per-tool view showing input code and stdout/stderr output
- Renders base64 PNG charts inline when the tool result contains `CHART[n]: data:image/png;...`
