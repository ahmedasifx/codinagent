"""
Coding agent: LangGraph ReAct agent with E2B sandbox for safe code execution.
Model is served via OpenRouter (OpenAI-compatible API).

Workflows: a lightweight router node classifies each request as
landing_page / fullstack / general and injects a workflow-specific
addendum into the system prompt. Same tool set for every workflow.
"""

import os
import re
import time
from typing import Annotated, TypedDict, AsyncIterator

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from e2b_code_interpreter import Sandbox

load_dotenv()

# ── Model via OpenRouter ───────────────────────────────────────────────────────
def get_llm(streaming: bool = True) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-coder"),
        openai_api_key=os.environ["OPENROUTER_API_KEY"],
        openai_api_base="https://openrouter.ai/api/v1",
        streaming=streaming,
        temperature=0,
        # OpenRouter-specific headers passed via model_kwargs
        model_kwargs={
            "extra_headers": {
                "HTTP-Referer": "https://coding-agent.local",
                "X-Title": "Coding Agent",
            }
        },
    )


# ── E2B sandbox ────────────────────────────────────────────────────────────────
# Module-level singleton: fine for a single-user local app. Multi-user would
# need per-session sandboxes keyed by a session id.
_sandbox: Sandbox | None = None
# Background dev servers keyed by port: {port: {"handle": ..., "logs": [...]}}
_background_processes: dict[int, dict] = {}


def get_sandbox() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        # Default sandbox timeout is 300s — too short for npm installs.
        _sandbox = Sandbox(api_key=os.environ["E2B_API_KEY"], timeout=600)
    return _sandbox


def close_sandbox():
    global _sandbox
    for proc in _background_processes.values():
        try:
            proc["handle"].kill()
        except Exception:
            pass
    _background_processes.clear()
    if _sandbox is not None:
        try:
            _sandbox.kill()
        except Exception:
            pass
        _sandbox = None


# ── Tools ──────────────────────────────────────────────────────────────────────
@tool
def execute_python(code: str) -> str:
    """Execute Python code in a secure E2B sandbox and return stdout, stderr, and results.

    Use this for: running scripts, testing functions, doing calculations,
    generating charts (returns base64). The sandbox persists within a session
    so variables are shared between calls.
    """
    sbx = get_sandbox()
    execution = sbx.run_code(code)

    output_parts = []

    if execution.logs.stdout:
        output_parts.append("STDOUT:\n" + "\n".join(execution.logs.stdout))

    if execution.logs.stderr:
        output_parts.append("STDERR:\n" + "\n".join(execution.logs.stderr))

    if execution.error:
        output_parts.append(f"ERROR: {execution.error.name}: {execution.error.value}")
        if execution.error.traceback:
            output_parts.append("TRACEBACK:\n" + execution.error.traceback)

    if execution.results:
        for i, result in enumerate(execution.results):
            if result.png:
                output_parts.append(f"CHART[{i}]: data:image/png;base64,{result.png}")
            elif result.text:
                output_parts.append(f"RESULT[{i}]: {result.text}")

    return "\n\n".join(output_parts) if output_parts else "Code executed with no output."


@tool
def install_package(package: str) -> str:
    """Install a Python package in the sandbox using pip. Use before importing packages."""
    sbx = get_sandbox()
    execution = sbx.run_code(f"!pip install {package} -q")
    stdout = "\n".join(execution.logs.stdout or [])
    if execution.error:
        return f"Install failed: {execution.error.value}"
    return f"Installed {package}.\n{stdout}" if stdout else f"Installed {package}."


@tool
def run_command(command: str, cwd: str = None, timeout: int = 120) -> str:
    """Run a shell command in the sandbox and return stdout/stderr/exit code.

    Use for: npm install, mkdir, mv, curl, pip, git, etc.
    Do NOT use for long-running processes like dev servers — use start_server instead.
    """
    sbx = get_sandbox()
    try:
        result = sbx.commands.run(command, cwd=cwd, timeout=timeout)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.exit_code
    except Exception as e:
        # e2b raises CommandExitException on non-zero exit; surface its output
        stdout = getattr(e, "stdout", "")
        stderr = getattr(e, "stderr", str(e))
        exit_code = getattr(e, "exit_code", 1)

    parts = [f"EXIT CODE: {exit_code}"]
    if stdout:
        parts.append("STDOUT:\n" + stdout)
    if stderr:
        parts.append("STDERR:\n" + stderr)
    return "\n\n".join(parts)


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox filesystem. Creates parent directories automatically."""
    sbx = get_sandbox()
    sbx.files.write(path, content)
    return f"Wrote {len(content)} bytes to {path}"


@tool
def read_file(path: str) -> str:
    """Read a file from the sandbox filesystem."""
    sbx = get_sandbox()
    try:
        return sbx.files.read(path)
    except Exception:
        return f"File not found: {path}"


@tool
def list_files(path: str = ".") -> str:
    """List files and directories at a path in the sandbox filesystem."""
    sbx = get_sandbox()
    try:
        entries = sbx.files.list(path)
    except Exception as e:
        return f"Cannot list {path}: {e}"
    if not entries:
        return f"(empty directory: {path})"
    lines = []
    for entry in entries:
        is_dir = str(getattr(entry, "type", "")).lower().endswith("dir")
        lines.append(f"{'[dir] ' if is_dir else '      '}{entry.name}")
    return "\n".join(lines)


@tool
def start_server(command: str, port: int, cwd: str = None) -> str:
    """Start a long-running server in the background and return a public preview URL.

    Use for dev servers and APIs, e.g.:
      - Vite:    start_server("npm run dev -- --host --port 5173", 5173, cwd="/home/user/app")
      - Static:  start_server("python3 -m http.server 8000", 8000, cwd="/home/user/app")
      - FastAPI: start_server("uvicorn main:app --host 0.0.0.0 --port 8000", 8000, cwd="/home/user/app")

    Servers must bind to 0.0.0.0 (or pass --host for Vite) to be reachable.
    Restarting on the same port kills the previous server first.
    """
    sbx = get_sandbox()

    # Restart support: kill any existing server on this port
    existing = _background_processes.pop(port, None)
    if existing is not None:
        try:
            existing["handle"].kill()
        except Exception:
            pass

    logs: list[str] = []
    handle = sbx.commands.run(
        command,
        cwd=cwd,
        background=True,
        on_stdout=lambda line: logs.append(line),
        on_stderr=lambda line: logs.append(line),
    )
    _background_processes[port] = {"handle": handle, "logs": logs}

    # Keep the sandbox alive while the user inspects the preview
    sbx.set_timeout(3600)

    # Poll until the port answers (~20s)
    ready = False
    for _ in range(10):
        time.sleep(2)
        try:
            check = sbx.commands.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}",
                timeout=10,
            )
            if check.stdout.strip() not in ("", "000"):
                ready = True
                break
        except Exception:
            continue

    log_tail = "\n".join(logs[-30:])
    if not ready:
        return (
            f"Server did not respond on port {port} after 20s. "
            f"Check the logs, fix the issue, and call start_server again.\n\n"
            f"SERVER LOGS:\n{log_tail or '(no output captured)'}"
        )

    url = f"https://{sbx.get_host(port)}"
    return f"Server running on port {port}.\n\nSERVER LOGS:\n{log_tail}\n\nPREVIEW_URL: {url}"


@tool
def stop_server(port: int) -> str:
    """Stop a background server previously started with start_server."""
    proc = _background_processes.pop(port, None)
    if proc is None:
        return f"No server tracked on port {port}."
    try:
        proc["handle"].kill()
    except Exception:
        pass
    return f"Stopped server on port {port}."


TOOLS = [
    execute_python,
    install_package,
    run_command,
    write_file,
    read_file,
    list_files,
    start_server,
    stop_server,
]

SYSTEM_PROMPT = """You are an expert coding agent. You have access to a secure Linux sandbox via E2B with Python, Node.js, and npm preinstalled, plus internet access. The sandbox persists for the conversation session.

## Your tools
- execute_python: run Python code (variables persist across calls)
- install_package: pip install Python packages
- run_command: any shell command (npm install, mkdir, curl, git, ...) — NOT for servers
- write_file / read_file / list_files: manage files in the sandbox
- start_server: launch a dev server / API in the background and get a public PREVIEW_URL
- stop_server: stop a background server

## Behaviour
1. Break the problem into clear steps and explain your plan briefly.
2. Write clean, well-structured code. Put projects under /home/user/app.
3. After execution, interpret the output for the user in plain language.
4. If code fails, diagnose the error and fix it — don't ask the user to fix it.
5. For charts or visualisations, use matplotlib; output includes a base64 PNG.
6. Always prefer to show a working result over asking clarifying questions.
7. When you build anything web-facing, ALWAYS finish by calling start_server and reporting the preview URL to the user.

## Server recipes (important)
- Servers must bind to 0.0.0.0 to be reachable through the sandbox proxy.
- Vite: vite.config.js MUST include `server: { host: true, allowedHosts: true }`, then start_server("npm run dev -- --host --port 5173", 5173, cwd=project_dir).
- Static site: start_server("python3 -m http.server 8000", 8000, cwd=project_dir).
- FastAPI: start_server("uvicorn main:app --host 0.0.0.0 --port 8000", 8000, cwd=project_dir)."""


WORKFLOW_PROMPTS = {
    "landing_page": """

## Current workflow: LANDING PAGE
Build the page as a React + Vite app (unless the user explicitly asks for plain HTML):
1. Scaffold files manually under /home/user/app with write_file — package.json, vite.config.js, index.html, src/main.jsx, src/App.jsx, src/index.css. Do NOT use interactive `npm create vite`.
2. vite.config.js must include `server: { host: true, allowedHosts: true }`.
3. run_command("npm install", cwd="/home/user/app") — this can take a minute.
4. start_server("npm run dev -- --host --port 5173", 5173, cwd="/home/user/app").
5. Report the preview URL. On follow-up feedback, edit the relevant files with write_file — Vite hot-reloads, no restart needed.
Make the page visually polished: real copy, a hero section, sensible color palette, responsive layout.""",
    "fullstack": """

## Current workflow: FULLSTACK APP
Build a FastAPI backend that serves BOTH the API and the static frontend on ONE port (no CORS, no second server):
1. Scaffold under /home/user/app: main.py (FastAPI with API routes + StaticFiles mount at "/") and a static/ dir with index.html, style.css, app.js that call the API with fetch().
2. run_command("pip install fastapi uvicorn", cwd="/home/user/app") if needed.
3. Test API endpoints with run_command using curl against localhost BEFORE exposing the preview.
4. start_server("uvicorn main:app --host 0.0.0.0 --port 8000", 8000, cwd="/home/user/app").
5. Report the preview URL and summarize the API endpoints.""",
    "general": "",
}


# ── LangGraph state & graph ────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    workflow: str


ROUTER_PROMPT = """Classify the user's request into exactly one category. Reply with ONLY the category name.

Categories:
- landing_page: build/modify a landing page, marketing page, portfolio, or static website UI
- fullstack: build/modify an app with backend logic (API, database, CRUD) plus a frontend
- general: everything else (scripts, data analysis, algorithms, questions, charts)

User request: {request}"""


def classify_workflow(text: str) -> str:
    try:
        llm = get_llm(streaming=False)
        response = llm.invoke(
            [HumanMessage(content=ROUTER_PROMPT.format(request=text))]
        )
        answer = response.content.strip().lower()
        for wf in ("landing_page", "fullstack", "general"):
            if wf in answer:
                return wf
    except Exception:
        pass
    return "general"


def build_graph():
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    tools_by_name = {t.name: t for t in TOOLS}

    def route(state: AgentState):
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        workflow = classify_workflow(last_human.content) if last_human else "general"
        return {"workflow": workflow}

    def call_model(state: AgentState):
        prompt = SYSTEM_PROMPT + WORKFLOW_PROMPTS.get(state.get("workflow", "general"), "")
        messages = [SystemMessage(content=prompt)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def call_tools(state: AgentState):
        last = state["messages"][-1]
        results = []
        for tool_call in last.tool_calls:
            tool_fn = tools_by_name[tool_call["name"]]
            try:
                result = tool_fn.invoke(tool_call["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            results.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        return {"messages": results}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("route", route)
    graph.add_node("agent", call_model)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("route")
    graph.add_edge("route", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


GRAPH = build_graph()

PREVIEW_URL_RE = re.compile(r"PREVIEW_URL: (https://\S+)")


# ── Streaming runner ───────────────────────────────────────────────────────────
async def run_agent_stream(message: str, history: list[dict]) -> AsyncIterator[dict]:
    """
    Stream agent events as dicts:
      {"type": "token",    "content": "..."}
      {"type": "workflow", "workflow": "landing_page" | "fullstack" | "general"}
      {"type": "tool_call", "name": "...", "args": {...}}
      {"type": "tool_result", "content": "..."}
      {"type": "preview",  "url": "https://..."}
      {"type": "done"}
      {"type": "error",    "content": "..."}
    """
    # Rebuild message history
    lc_messages: list[AnyMessage] = []
    for msg in history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            from langchain_core.messages import AIMessage
            lc_messages.append(AIMessage(content=msg["content"]))

    lc_messages.append(HumanMessage(content=message))

    try:
        async for event in GRAPH.astream_events(
            {"messages": lc_messages, "workflow": "general"}, version="v2"
        ):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chat_model_stream":
                # Only stream tokens from the main agent node (the router also
                # makes an LLM call whose tokens must not leak to the user).
                if event.get("metadata", {}).get("langgraph_node") != "agent":
                    continue
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield {"type": "token", "content": chunk.content}

            elif kind == "on_chain_end" and name == "route":
                output = event["data"].get("output") or {}
                if isinstance(output, dict) and output.get("workflow"):
                    yield {"type": "workflow", "workflow": output["workflow"]}

            elif kind == "on_tool_start":
                yield {
                    "type": "tool_call",
                    "name": name,
                    "args": event["data"].get("input", {}),
                }

            elif kind == "on_tool_end":
                output = str(event["data"].get("output", ""))
                yield {"type": "tool_result", "content": output}
                match = PREVIEW_URL_RE.search(output)
                if match:
                    yield {"type": "preview", "url": match.group(1)}

        yield {"type": "done"}

    except Exception as e:
        yield {"type": "error", "content": str(e)}
