"""Railway sandbox bridge client.

All sandbox execution runs on Railway Sandboxes. This module is a thin HTTP client
for the railway-bridge sidecar, which holds the actual Railway Sandbox objects;
Python just sends it HTTP requests.
"""

import httpx

from .config import get_settings

DEFAULT_SESSION = "default"


def _bridge_url(path: str) -> str:
    return f"{get_settings().railway_bridge_url.rstrip('/')}/{path.lstrip('/')}"


# First param is prefixed to avoid colliding with kwargs of the same name (the file
# endpoints send a `path` field, which used to shadow this and blow up _post).
def _post(_endpoint: str, **json_fields) -> dict:
    resp = httpx.post(_bridge_url(_endpoint), json=json_fields, timeout=180)
    resp.raise_for_status()
    return resp.json()


def _get(_endpoint: str, **params) -> httpx.Response:
    resp = httpx.get(_bridge_url(_endpoint), params=params, timeout=60)
    resp.raise_for_status()
    return resp


def _delete(_endpoint: str, **params) -> dict:
    resp = httpx.delete(_bridge_url(_endpoint), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Session manager (thin — real state lives in the bridge) ───────────────────

class SandboxManager:
    def __init__(self) -> None:
        self._sessions: set[str] = set()

    def get(self, session_id: str = DEFAULT_SESSION) -> str:
        self._sessions.add(session_id)
        return session_id

    def close(self, session_id: str = DEFAULT_SESSION) -> None:
        self._sessions.discard(session_id)
        try:
            _delete("sandbox", session_id=session_id)
        except Exception:
            pass

    def close_all(self) -> None:
        self._sessions.clear()
        try:
            _delete("sandbox/all")
        except Exception:
            pass


MANAGER = SandboxManager()


# ── Backward-compatible helpers ───────────────────────────────────────────────

def get_sandbox(session_id: str = DEFAULT_SESSION) -> str:
    return MANAGER.get(session_id)


def close_sandbox(session_id: str = DEFAULT_SESSION) -> None:
    MANAGER.close(session_id)


# ── Bridge call helpers ───────────────────────────────────────────────────────

def bridge_exec(
    command: str,
    session_id: str = DEFAULT_SESSION,
    cwd: str | None = None,
    timeout: int = 120,
) -> dict:
    return _post("exec", session_id=session_id, command=command, cwd=cwd, timeout=timeout)


def bridge_exec_python(code: str, session_id: str = DEFAULT_SESSION) -> dict:
    return _post("exec-python", session_id=session_id, code=code)


def bridge_start_server(
    command: str,
    port: int,
    cwd: str | None = None,
    session_id: str = DEFAULT_SESSION,
) -> dict:
    return _post(
        "start-server",
        session_id=session_id,
        command=command,
        port=port,
        cwd=cwd,
    )


def bridge_stop_server(port: int, session_id: str = DEFAULT_SESSION) -> dict:
    return _post("stop-server", session_id=session_id, port=port)


def bridge_write_file(
    path: str, content: str, session_id: str = DEFAULT_SESSION
) -> dict:
    return _post("files/write", session_id=session_id, path=path, content=content)


def bridge_read_file(path: str, session_id: str = DEFAULT_SESSION) -> str:
    resp = _get("files/read", session_id=session_id, path=path)
    return resp.text


def bridge_list_files(
    path: str = ".", session_id: str = DEFAULT_SESSION
) -> list[dict]:
    resp = _get("files/list", session_id=session_id, path=path)
    return resp.json()
