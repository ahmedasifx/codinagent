"""Remotion render tool — drives `npx remotion render` in the sandbox, copies the
rendered file out to the artifact store, and returns an ARTIFACT: marker that the
runner turns into an `artifact` SSE event.
"""

import json

from langchain_core.tools import tool

from ...core.artifacts import store_bytes
from ...core.db import db_enabled, session_scope
from ...core.sandbox import get_sandbox
from ...registries.tool_registry import register_tool

# Chromium runtime libs Remotion's headless renderer needs on Debian/Ubuntu.
_CHROME_DEPS = (
    "libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libgbm1 "
    "libasound2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxkbcommon0 "
    "libatspi2.0-0 libpango-1.0-0 libcairo2 fonts-liberation"
)
# Track sandboxes we've already provisioned to skip the slow apt step on retries.
_provisioned: set[int] = set()


def _ensure_browser(sbx, project_dir: str) -> str:
    """Install Chromium system deps + download Remotion's browser. Idempotent; best
    effort (returns logs that are only surfaced if the subsequent render fails)."""
    if id(sbx) in _provisioned:
        # Still ensure the browser binary exists (cheap no-op once downloaded).
        try:
            r = sbx.commands.run("npx remotion browser ensure", cwd=project_dir, timeout=600)
            return r.stdout or ""
        except Exception as e:
            return getattr(e, "stderr", str(e))

    apt = (
        f"(sudo apt-get update -qq && sudo apt-get install -y -qq {_CHROME_DEPS}) "
        f"|| (apt-get update -qq && apt-get install -y -qq {_CHROME_DEPS})"
    )
    logs = []
    for cmd in (apt, "npx remotion browser ensure"):
        try:
            r = sbx.commands.run(cmd, cwd=project_dir, timeout=900)
            logs.append(r.stdout or "")
        except Exception as e:
            logs.append(getattr(e, "stderr", str(e)))
    _provisioned.add(id(sbx))
    return "\n".join(logs)


def _read_bytes(sbx, path: str) -> bytes | None:
    for kwargs in ({"format": "bytes"}, {}):
        try:
            data = sbx.files.read(path, **kwargs)
            if isinstance(data, str):
                data = data.encode("latin-1", errors="ignore")
            return data
        except Exception:
            continue
    return None


@register_tool
@tool
def render_remotion(
    project_dir: str,
    composition_id: str,
    entry: str = "src/index.ts",
    out: str = "out/video.mp4",
) -> str:
    """Render a Remotion composition to a video file and store it as a downloadable artifact.

    Prerequisites (do these first with the other tools):
      1. write_file the Remotion project under project_dir (package.json, src/index.ts
         registering the root, src/Root.tsx with <Composition id=...>, scene components).
      2. run_command("npm install", cwd=project_dir) — installs remotion + deps (slow).

    Then call this tool with the composition id. Returns a preview/download URL for the
    rendered mp4. Use mp4 for video, or .webm/.gif via the `out` extension.
    """
    sbx = get_sandbox()
    sbx.set_timeout(3600)  # rendering is slow; keep the sandbox alive

    # Headless Chromium (libs + browser binary) must be present before rendering.
    prep_logs = _ensure_browser(sbx, project_dir)

    cmd = f"npx remotion render {entry} {composition_id} {out} --log=info"
    try:
        result = sbx.commands.run(cmd, cwd=project_dir, timeout=1800)
        stdout, stderr, code = result.stdout, result.stderr, result.exit_code
    except Exception as e:
        stdout = getattr(e, "stdout", "")
        stderr = getattr(e, "stderr", str(e))
        code = getattr(e, "exit_code", 1)

    if code != 0:
        tail = (stderr or stdout)[-2000:]
        prep_tail = prep_logs[-800:] if prep_logs else ""
        return (
            f"Render failed (exit {code}). Fix and retry.\n\n"
            f"RENDER LOGS:\n{tail}\n\nBROWSER SETUP LOGS:\n{prep_tail}"
        )

    abs_out = out if out.startswith("/") else f"{project_dir.rstrip('/')}/{out}"
    data = _read_bytes(sbx, abs_out)
    if not data:
        return f"Render reported success but {abs_out} could not be read from the sandbox."

    ext = out.rsplit(".", 1)[-1].lower()
    mime = {"mp4": "video/mp4", "webm": "video/webm", "gif": "image/gif"}.get(
        ext, "application/octet-stream"
    )
    kind = "image" if ext == "gif" else "video"
    art = store_bytes(data, kind=kind, mime=mime, ext=ext)

    if db_enabled():
        try:
            from ...models import Artifact

            with session_scope() as session:
                session.add(
                    Artifact(
                        type=kind,
                        uri=art.path,
                        mime=mime,
                        meta={"composition_id": composition_id},
                    )
                )
        except Exception:
            pass

    url = f"/artifacts/{art.id}/download"
    marker = json.dumps(
        {"artifact_id": art.id, "kind": kind, "mime": mime, "url": url}
    )
    return (
        f"Rendered composition '{composition_id}' ({len(data)} bytes).\n"
        f"Download/preview: {url}\nARTIFACT:{marker}"
    )
