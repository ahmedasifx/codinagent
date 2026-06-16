"""Built-in sandbox tools (E2B). Migrated verbatim in behaviour from the original
agent.py, now registered into the ToolRegistry via `register_tool`."""

from langchain_core.tools import tool

from ...core.sandbox import background_processes, get_sandbox, wait_for_port
from ...registries.tool_registry import register_tool


@register_tool
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


@register_tool
@tool
def install_package(package: str) -> str:
    """Install a Python package in the sandbox using pip. Use before importing packages."""
    sbx = get_sandbox()
    execution = sbx.run_code(f"!pip install {package} -q")
    stdout = "\n".join(execution.logs.stdout or [])
    if execution.error:
        return f"Install failed: {execution.error.value}"
    return f"Installed {package}.\n{stdout}" if stdout else f"Installed {package}."


@register_tool
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
        stdout = getattr(e, "stdout", "")
        stderr = getattr(e, "stderr", str(e))
        exit_code = getattr(e, "exit_code", 1)

    parts = [f"EXIT CODE: {exit_code}"]
    if stdout:
        parts.append("STDOUT:\n" + stdout)
    if stderr:
        parts.append("STDERR:\n" + stderr)
    return "\n\n".join(parts)


@register_tool
@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox filesystem. Creates parent directories automatically."""
    sbx = get_sandbox()
    sbx.files.write(path, content)
    return f"Wrote {len(content)} bytes to {path}"


@register_tool
@tool
def read_file(path: str) -> str:
    """Read a file from the sandbox filesystem."""
    sbx = get_sandbox()
    try:
        return sbx.files.read(path)
    except Exception:
        return f"File not found: {path}"


@register_tool
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


@register_tool
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
    procs = background_processes()

    existing = procs.pop(port, None)
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
    procs[port] = {"handle": handle, "logs": logs}

    # Keep the sandbox alive while the user inspects the preview
    sbx.set_timeout(3600)

    ready = wait_for_port(sbx, port)
    log_tail = "\n".join(logs[-30:])
    if not ready:
        return (
            f"Server did not respond on port {port} after 20s. "
            f"Check the logs, fix the issue, and call start_server again.\n\n"
            f"SERVER LOGS:\n{log_tail or '(no output captured)'}"
        )

    url = f"https://{sbx.get_host(port)}"
    return f"Server running on port {port}.\n\nSERVER LOGS:\n{log_tail}\n\nPREVIEW_URL: {url}"


@register_tool
@tool
def stop_server(port: int) -> str:
    """Stop a background server previously started with start_server."""
    procs = background_processes()
    proc = procs.pop(port, None)
    if proc is None:
        return f"No server tracked on port {port}."
    try:
        proc["handle"].kill()
    except Exception:
        pass
    return f"Stopped server on port {port}."
