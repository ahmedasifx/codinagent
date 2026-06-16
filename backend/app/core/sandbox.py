"""E2B sandbox management.

Generalizes the original module-level singleton into a session-keyed manager.
For the current single-user app there is one "default" session, so behaviour is
identical to before; multi-user simply passes a real session id.
"""

import time

from e2b_code_interpreter import Sandbox

from .config import get_settings

DEFAULT_SESSION = "default"


class _SandboxSession:
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox
        # Background dev servers keyed by port: {port: {"handle": ..., "logs": [...]}}
        self.background: dict[int, dict] = {}


class SandboxManager:
    def __init__(self) -> None:
        self._sessions: dict[str, _SandboxSession] = {}

    def get(self, session_id: str = DEFAULT_SESSION) -> Sandbox:
        sess = self._sessions.get(session_id)
        if sess is None:
            # Default sandbox timeout is 300s — too short for npm installs.
            sbx = Sandbox(api_key=get_settings().e2b_api_key, timeout=600)
            sess = _SandboxSession(sbx)
            self._sessions[session_id] = sess
        return sess.sandbox

    def background(self, session_id: str = DEFAULT_SESSION) -> dict[int, dict]:
        self.get(session_id)  # ensure session exists
        return self._sessions[session_id].background

    def close(self, session_id: str = DEFAULT_SESSION) -> None:
        sess = self._sessions.pop(session_id, None)
        if sess is None:
            return
        for proc in sess.background.values():
            try:
                proc["handle"].kill()
            except Exception:
                pass
        try:
            sess.sandbox.kill()
        except Exception:
            pass

    def close_all(self) -> None:
        for sid in list(self._sessions.keys()):
            self.close(sid)


MANAGER = SandboxManager()


# ── Backward-compatible helpers (default session) ───────────────────────────────
def get_sandbox(session_id: str = DEFAULT_SESSION) -> Sandbox:
    return MANAGER.get(session_id)


def background_processes(session_id: str = DEFAULT_SESSION) -> dict[int, dict]:
    return MANAGER.background(session_id)


def close_sandbox(session_id: str = DEFAULT_SESSION) -> None:
    MANAGER.close(session_id)


def wait_for_port(sandbox: Sandbox, port: int, attempts: int = 10) -> bool:
    """Poll until an HTTP port answers (~2s * attempts)."""
    for _ in range(attempts):
        time.sleep(2)
        try:
            check = sandbox.commands.run(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}",
                timeout=10,
            )
            if check.stdout.strip() not in ("", "000"):
                return True
        except Exception:
            continue
    return False
