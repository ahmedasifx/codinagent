# AI Agent Platform — Architecture & Design Notes

> Personal experimentation project. Single-user, local-first. Goal: autonomous,
> long-horizon tool-using agents in the spirit of Hermes-class models.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + LangGraph + LangChain |
| LLM access | OpenRouter (OpenAI-compatible, model-agnostic) |
| Code execution | E2B cloud sandbox (Python kernel + shell) |
| Video rendering | Remotion (React-based programmatic video) |
| Text-to-speech | TTS tool (optional, per skill) |
| Persistence | PostgreSQL + pgvector (optional — DB-less mode works) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | React 18 + TypeScript + Vite |

---

## Directory Layout

```
backend/
  app/
    main.py                 # FastAPI app + CORS + lifespan (load_builtins)
    api/
      chat.py               # POST /agents/{slug}/chat/stream + /chat/stream alias
      agents.py             # CRUD: /agents, /skills
      artifacts.py          # GET /artifacts/{id}/download
      credentials.py
      mcp.py
      tools.py
    engine/
      graph.py              # build_agent_graph() — per-agent LangGraph compiler
      nodes.py              # make_select_node, make_agent_node, make_tools_node
      runner.py             # run_agent_stream() — SSE event producer
      state.py              # AgentState TypedDict
      context.py            # assemble_system_prompt()
      planner.py            # generate_plan(), resolve_planning_mode()
      llm.py                # get_llm() — OpenRouter ChatOpenAI
    registries/
      agent_registry.py     # AgentRegistry (core + custom DB agents)
      skill_registry.py     # SkillRegistry
      tool_registry.py      # ToolRegistry
      loader.py             # load_builtins() — convention-driven auto-import
      types.py              # AgentDef, SkillDef (pure dataclasses)
    agents/                 # register_agent() calls — one file per agent
    skills/                 # register_skill() calls — one dir per domain
    tools/internal/         # register_tool() calls — @tool decorated functions
    core/
      config.py             # Settings (env-based, lru_cache)
      sandbox.py            # SandboxManager (session-keyed E2B wrapper)
      db.py                 # SQLAlchemy engine, session_scope, db_enabled()
      artifacts.py          # local artifact store (swappable for S3)
    memory/
      store.py              # save() + recall() — pgvector + ILIKE fallback
    models/                 # SQLAlchemy ORM: Agent, Skill, Conversation, Message, Run, Memory
  alembic/                  # DB migrations

frontend/src/
  App.tsx                   # Layout, agent/planning picker, AgentBuilder
  hooks/useAgent.ts         # SSE client, all state management, plan approval flow
  components/
    MessageBubble.tsx       # Renders tokens, tool calls, plans, artifacts, approval UI
    PreviewPanel.tsx        # iframe for sandbox live preview
    ToolCallPanel.tsx       # Collapsible tool I/O; base64 PNG charts inline
    ArtifactPanel.tsx       # Download links for generated files
    PlanPanel.tsx           # Plan display + approve/reject
    AgentBuilder.tsx        # No-code custom agent creator UI
  types/index.ts            # AgentEvent union — must mirror runner.py
```

---

## Core Architecture

### Three-Registry Pattern

Everything is data-driven through three registries. Adding capability = writing a `register_*()` call; the engine is generic and never changes.

```
AgentDef  ──owns──▶  skills: [SkillDef slugs]
                     tools:  [ToolDef slugs]   (always-on)

SkillDef  ──owns──▶  required_tools: [ToolDef slugs]  (added per-turn)
                     sub_skills: [SkillDef slugs]       (composition)

ToolDef   ──is──▶   LangChain @tool function
```

`loader.load_builtins()` walks `app/tools/internal`, `app/skills`, `app/agents` on startup and imports every module, triggering all `register_*()` side effects.

### Per-Agent LangGraph Graph

```
                 ┌────────────────────────────────────┐
                 │           AgentState               │
                 │  messages, agent_slug,             │
                 │  selected_skill, recalled, plan    │
                 └────────────────────────────────────┘
                              │
                              ▼
                         ┌─────────┐
                         │ select  │  ← classifier LLM call (non-streaming)
                         │         │    picks the best SkillDef for the request
                         └────┬────┘
                              │ selected_skill slug
                              ▼
                         ┌─────────┐
                    ┌───▶│  agent  │  ← LLM bound to (agent.tools ∪ skill.required_tools)
                    │    │         │    system = identity + skill instructions + memory + plan
                    │    └────┬────┘
                    │         │ tool_calls?
                    │    yes  ▼
                    │    ┌─────────┐
                    └────│  tools  │  ← ToolRegistry.get_langchain_tool() + .invoke()
                         └─────────┘
                              │ no tool_calls → END
```

Graphs are compiled once per core agent slug and cached in `AgentRegistry._graph_cache`. Custom (DB-defined) agents are not cached.

### SSE Streaming Protocol

`runner.py` consumes `graph.astream_events(version="v2")` and maps LangGraph events to typed SSE dicts:

| Event type | Fields | Source |
|---|---|---|
| `agent_selected` | `agent` | always first |
| `skill_selected` | `skill` | `on_chain_end` from `select` node |
| `plan` | `plan` | planning step (if mode ≠ off) |
| `awaiting_approval` | — | planning mode = approve, before tools run |
| `token` | `content` | `on_chat_model_stream` from `agent` node only |
| `tool_call` | `name`, `args` | `on_tool_start` |
| `tool_result` | `content` | `on_tool_end` |
| `preview` | `url` | parsed from `PREVIEW_URL:` in tool output |
| `artifact` | `artifact_id`, `kind`, `url`, `mime` | parsed from `ARTIFACT:{...}` in tool output |
| `progress` | `label`, `pct?` | optional in-flight progress |
| `done` | — | terminal |
| `error` | `content` | terminal |

**Rule:** only `agent` node tokens reach the client (`langgraph_node == "agent"` guard). The `select` node is intentionally suppressed.

### Planning Modes

| Mode | Behavior |
|---|---|
| `off` | No plan generated, execute immediately |
| `auto` | Plan generated + injected into system prompt, execute in same turn |
| `approve` | Plan shown to user → emit `awaiting_approval` + `done`; on re-request with `approved_plan`, re-run in `execute` mode |

Note: `approve` mode is currently faked — on approval the entire graph re-runs from scratch with the plan injected. No mid-run interrupts yet.

### Context Assembly (`context.py`)

System prompt = concatenation of:
1. `agent.system_prompt` (identity)
2. `agent.instructions` + `agent.personality`
3. Selected skill's `instructions` (e.g. the full Remotion pipeline steps)
4. Recalled memory snippets (if `auto_recall` or agent carries `recall_memory` tool)
5. Approved plan (if mode = execute)

**Known gap:** no token budget / summarization. Tool outputs are dumped verbatim into messages; long runs degrade as the window fills.

### Memory (`memory/store.py`)

- `save(content, namespace)` — embeds with OpenAI embeddings via OpenRouter, stores in `Memory` table with pgvector column.
- `recall(query, k, namespace)` — cosine distance search; falls back to ILIKE keyword search if pgvector unavailable.
- `auto_recall` is **off by default**. Nothing calls `save()` automatically — memory only works if the agent explicitly invokes the `recall_memory`/`save_memory` tools.

### Sandbox Management (`core/sandbox.py`)

`SandboxManager` wraps E2B, session-keyed:

- `get(session_id)` — lazy create; rolling keep-alive (`set_timeout`) on every call; auto-recovers dead sandboxes.
- `background(session_id)` — tracks background processes (dev servers) by port.
- `close_all()` — called on app shutdown.

**Current limitation:** the API never passes a `session_id` — all users share `"default"`. Single-user only.

### Multi-Agent Delegation (`tools/internal/orchestration.py`)

`delegate_to_agent(agent_slug, task)` invokes a sub-agent's compiled graph synchronously via `graph.invoke()` and returns the last `AIMessage` content as a string.

**Current limitations:**
- Blocking (no streaming of sub-agent events to the UI)
- Returns only the final text — artifacts, previews, and tool calls from the sub-agent are lost
- No recursion guard (an agent could delegate to itself)
- No parallel delegation

---

## Agents

| Slug | Description | Skills | Key Tools |
|---|---|---|---|
| `orchestrator` | Routes to specialists, plans + delegates | none | `delegate_to_agent` |
| `coding_agent` | Code, data analysis, full-stack apps | `coding` | all sandbox tools |
| `landing_page` | Responsive landing pages with live preview | `landing_page` | sandbox + start_server |
| `marketing` | Instagram post images + captions | `instagram_post` | sandbox + save_artifact |
| `document` | Professional PDFs (CV, report, invoice) | `document` | sandbox + save_artifact |
| `infographic_video` | Animated infographic videos via Remotion | `create_infographic_video` (composite) | sandbox + render_remotion + tts |
| `mobile_app_demo` | (WIP, uncommitted) | mobile_app skills | TBD |

---

## Skills

### Infographic Video (most elaborate — 6 granular + 1 composite)

```
create_infographic_video  (composite entry point)
  ├── storyboard_generation     → storyboard.json
  ├── scene_definition          → per-scene layout/animation specs
  ├── remotion_component_generation → scaffold Remotion project + npm install
  ├── voiceover                 → tts() per scene into public/audio/
  ├── subtitle_generation       → animated captions in components
  └── video_rendering           → render_remotion() → MP4 artifact
```

### Instagram Post (3-step pipeline)
1. Copy (caption + on-image headline + hashtags)
2. Design (1080×1080 HTML/CSS)
3. Render PNG via headless Chromium/Playwright → save_artifact

---

## Tools

| Tool | Purpose |
|---|---|
| `execute_python` | Run Python in E2B kernel; returns stdout/stderr/base64 charts |
| `install_package` | pip install in sandbox |
| `run_command` | Shell command (npm, mkdir, curl…); not for long-running processes |
| `write_file` / `read_file` / `list_files` | Sandbox filesystem |
| `start_server` | Background dev server; polls until port answers; returns `PREVIEW_URL:` |
| `stop_server` | Kill background server by port |
| `render_remotion` | Render a Remotion composition to MP4; returns `ARTIFACT:` |
| `tts` | Text-to-speech → audio file |
| `save_artifact` | Copy sandbox file to artifact store; returns `ARTIFACT:` |
| `recall_memory` / `save_memory` | Long-term memory R/W |
| `delegate_to_agent` | Orchestrator handoff to a specialist agent |

---

## Database Schema (optional — DB-less mode works without)

```
agents           slug, name, description, instructions, personality,
                 system_prompt, model, config (JSONB), is_core, owner_id

skills           slug, name, description, instructions, when_to_use,
                 kind, config (JSONB), is_core, owner_id

tools            slug, name, description, config (JSONB), is_core

conversations    agent_id, agent_slug, title, owner_id
messages         conversation_id, role, content, tool_calls (JSONB), tool_call_id
runs             conversation_id, agent_slug, status, selected_skill,
                 started_at, finished_at, error

memory           namespace, content, embedding (vector), meta (JSONB)
artifacts        (local disk: artifact_store/{id}.{ext})
```

Skill/tool membership for custom agents is stored as slug lists in `agents.config` (`{"skills": [...], "tools": [...]}`), so custom agents can mix core (code-defined) and DB-defined slugs without FK constraints.

---

## Configuration (`.env`)

```bash
# LLM
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=deepseek/deepseek-coder      # any OpenRouter slug
OPENROUTER_FALLBACK_MODELS=deepseek/deepseek-v4-flash
EMBEDDING_MODEL=openai/text-embedding-3-small

# Sandbox
E2B_API_KEY=...
SANDBOX_TIMEOUT=1800

# Persistence (omit for DB-less mode)
DATABASE_URL=postgresql://...

# Platform
DEFAULT_AGENT=coding_agent
ARTIFACT_DIR=./artifact_store
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Frontend State (useAgent.ts)

Manages all SSE parsing and message state:

- **`messages`** — `ChatMessage[]`, accumulated from SSE events
- **`isRunning`** — true while SSE stream is open
- **`previewUrl`** — latest `PREVIEW_URL` for the iframe panel
- **`skill`** — active skill badge display
- **`agentSlug`** / **`setAgentSlug`** — which agent to route to
- **`planningMode`** — `off | auto | approve`
- **`approvePlan()`** — re-sends request with `approved_plan` field set
- **`rejectPlan()`** — clears the pending plan message
- **`stopGeneration()`** — aborts the fetch/SSE reader

---

## Known Gaps & Design Notes (from architecture review)

### What's missing for true autonomous operation

**Context management** (highest priority)
- Tool outputs are dumped verbatim into messages — no truncation, no summarization.
- A 15-step video pipeline fills the context window; the agent degrades silently.
- `context.py` has a TODO for this ("token budget / summarization step is layered in P2").

**No checkpointing / durable run state**
- History is rebuilt from client-supplied `history` every turn.
- No LangGraph checkpointer → no resumable runs, no real mid-run HITL.
- `approve` mode is faked: re-runs the full graph from scratch with the plan prepended.
- Fix: `AsyncPostgresSaver` checkpointer + `thread_id` keyed by conversation; use native `interrupt()` for approval.

**No self-correction loop**
- "Verify your work" exists only as prose in skill instructions.
- No structural critic/verifier node, no test→observe→fix cycle.
- This is the difference between a tool loop and an autonomous agent.

**Memory is passive**
- Nothing auto-saves memories after a run.
- `auto_recall` is off by default.
- No reflection/consolidation step.

**Delegation is synchronous and lossy**
- Sub-agent artifacts/previews don't surface to the orchestrating run's SSE stream.
- No parallel delegation.

**No observability**
- Langfuse is vendored but not integrated (ignore directory).
- No per-run cost or token accounting.

**Single-user sandbox**
- API never passes `session_id` → all requests share `"default"` sandbox.
- Two concurrent conversations stomp each other's filesystem.

### Recommended improvement order (for experimentation phase)

1. **Lightweight run logging** — dump full message list to JSON per run; instant visibility when debugging failures.
2. **Context truncation** — cap tool outputs at ~2000 chars, summarize older messages. Removes a silent confound.
3. **LangGraph checkpointer + thread_id** — unlocks durable state and real `interrupt()`-based approval.
4. **Verifier node** — structural self-correction after tool execution.
5. Multi-tenancy / sandbox isolation (only when productizing).

### Agent roadmap notes

Current agents ranked by differentiation:

| Agent | Assessment |
|---|---|
| `infographic_video` | Highest ceiling — programmatic Remotion video is the real moat |
| `landing_page` | Most reliable demo — live preview is instant wow |
| `marketing` | Sticky/high-frequency, but commoditized |
| `document` | Solid B2B utility, low virality |
| `coding_agent` | Table stakes — engine, not draw |

**Missing agents worth adding:**
- **Slide deck / presentation** — same "plan → rendered artifact" shape, massive demand (Gamma/Tome territory). Easiest high-value add.
- **Data analysis / insights** — already 80% there with `execute_python` + base64 charts. "Upload CSV → analysis + charts + written summary."
- **Audio / podcast** — TTS already exists; NotebookLM-style narrated audio from a doc/topic.
- **Diagram / architecture** — Mermaid → image artifact. Small, devs love it.

**Missing capability that caps all of them:** no web-search/fetch tool. Adding search unlocks a research/report agent and improves quality across the board.

---

## Running

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill E2B_API_KEY and OPENROUTER_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env  # VITE_API_URL=http://localhost:8000
npm run dev           # http://localhost:5173
```

**Docker:**
```bash
docker compose up --build
# frontend → :3000, backend → :8000
```

---

## Adding a New Agent (the pattern)

1. Create `backend/app/agents/my_agent.py` with a `register_agent(AgentDef(...))` call.
2. Create `backend/app/skills/my_agent/skills.py` with `register_skill(SkillDef(...))` calls.
3. Add any new tools to `backend/app/tools/internal/` with `@register_tool @tool` decorators.
4. `load_builtins()` on startup auto-discovers and imports all three.
5. Reference the new agent via `POST /agents/{slug}/chat/stream` or select it in the UI dropdown.

No engine changes required.
