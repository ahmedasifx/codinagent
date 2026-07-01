"""Built-in sandbox tools (Railway). Calls the railway-bridge sidecar via HTTP."""

from langchain_core.tools import tool

from ...core.sandbox import (
    bridge_exec,
    bridge_exec_python,
    bridge_list_files,
    bridge_read_file,
    bridge_start_server,
    bridge_stop_server,
    bridge_write_file,
)
from ...registries.tool_registry import register_tool


@register_tool
@tool
def execute_python(code: str) -> str:
    """Execute Python code in a secure Railway sandbox and return stdout/stderr.

    Each call runs a fresh python3 process — variables do NOT persist between calls.
    Write self-contained scripts. For charts, use matplotlib with savefig:
      plt.savefig('/tmp/chart.png', dpi=150)
      import base64
      with open('/tmp/chart.png','rb') as f:
          print('CHART[0]: data:image/png;base64,' + base64.b64encode(f.read()).decode())
    """
    result = bridge_exec_python(code)

    parts: list[str] = []
    if result.get("stdout"):
        parts.append("STDOUT:\n" + result["stdout"])
    if result.get("stderr"):
        parts.append("STDERR:\n" + result["stderr"])
    if result.get("exit_code", 0) != 0:
        parts.append(f"EXIT CODE: {result['exit_code']}")
    return "\n\n".join(parts) if parts else "Code executed with no output."


@register_tool
@tool
def install_package(package: str) -> str:
    """Install a Python package in the sandbox using pip. Use before importing packages."""
    result = bridge_exec(f"pip install {package} -q")
    if result.get("exit_code", 0) != 0:
        return f"Install failed:\n{result.get('stderr', '')}"
    stdout = result.get("stdout", "").strip()
    return f"Installed {package}." + (f"\n{stdout}" if stdout else "")


@register_tool
@tool
def run_command(command: str, cwd: str = None, timeout: int = 120) -> str:
    """Run a shell command in the sandbox and return stdout/stderr/exit code.

    Use for: npm install, mkdir, mv, curl, pip, git, etc.
    Do NOT use for long-running processes like dev servers — use start_server instead.
    """
    result = bridge_exec(command, cwd=cwd, timeout=timeout)

    parts = [f"EXIT CODE: {result.get('exit_code', '?')}"]
    if result.get("stdout"):
        parts.append("STDOUT:\n" + result["stdout"])
    if result.get("stderr"):
        parts.append("STDERR:\n" + result["stderr"])
    return "\n\n".join(parts)


@register_tool
@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox filesystem. Creates parent directories automatically."""
    bridge_write_file(path, content)
    return f"Wrote {len(content)} bytes to {path}"


@register_tool
@tool
def read_file(path: str) -> str:
    """Read a file from the sandbox filesystem."""
    try:
        return bridge_read_file(path)
    except Exception:
        return f"File not found: {path}"


@register_tool
@tool
def list_files(path: str = ".") -> str:
    """List files and directories at a path in the sandbox filesystem."""
    try:
        entries = bridge_list_files(path)
    except Exception as e:
        return f"Cannot list {path}: {e}"
    if not entries:
        return f"(empty directory: {path})"
    lines = [
        f"{'[dir] ' if e.get('is_dir') else '      '}{e['name']}"
        for e in entries
    ]
    return "\n".join(lines)


@register_tool
@tool
def start_server(command: str, port: int, cwd: str = None) -> str:
    """Start a long-running server in the background and return a public preview URL.

    Use for dev servers and APIs, e.g.:
      - Vite:    start_server("npm run dev -- --host --port 5173", 5173, cwd="/home/user/app")
      - Static:  start_server("python3 -m http.server 8000", 8000, cwd="/home/user/app")
      - FastAPI: start_server("uvicorn main:app --host 0.0.0.0 --port 8000", 8000, cwd="/home/user/app")

    Servers must bind to 0.0.0.0 to be reachable. Restarting on the same port kills
    the previous server first. A Cloudflare tunnel provides the public preview URL.
    """
    result = bridge_start_server(command, port, cwd=cwd)
    log_tail = result.get("logs", "")

    if not result.get("ready"):
        return (
            f"Server did not respond on port {port} after 20s. "
            f"Check the logs, fix the issue, and call start_server again.\n\n"
            f"SERVER LOGS:\n{log_tail or '(no output captured)'}"
        )

    url = result.get("preview_url", "")
    if url:
        return (
            f"Server running on port {port}.\n\n"
            f"SERVER LOGS:\n{log_tail}\n\n"
            f"PREVIEW_URL: {url}"
        )
    return (
        f"Server running on port {port} (Cloudflare tunnel unavailable — no public URL).\n\n"
        f"SERVER LOGS:\n{log_tail}"
    )


@register_tool
@tool
def stop_server(port: int) -> str:
    """Stop a background server previously started with start_server."""
    result = bridge_stop_server(port)
    if result.get("stopped"):
        return f"Stopped server on port {port}."
    return f"No server tracked on port {port}."
