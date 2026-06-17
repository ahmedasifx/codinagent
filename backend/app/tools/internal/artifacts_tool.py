"""Generic artifact tool — register a file produced in the sandbox as a downloadable
artifact (image/pdf/video/audio). Lets any agent emit downloads without bespoke tools.
"""

import json
import os

from langchain_core.tools import tool

from ...core.artifacts import store_bytes
from ...core.db import db_enabled, session_scope
from ...core.sandbox import get_sandbox
from ...registries.tool_registry import register_tool

_MIME = {
    "image": ("png", "image/png"),
    "pdf": ("pdf", "application/pdf"),
    "video": ("mp4", "video/mp4"),
    "audio": ("mp3", "audio/mpeg"),
}


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
def save_artifact(sandbox_path: str, kind: str = "image") -> str:
    """Save a file produced in the sandbox as a downloadable artifact and return its URL.

    Call after you've written the output file (PNG/PDF/MP4/MP3) in the sandbox.
    `kind` is one of: image, pdf, video, audio. Returns a download URL for the user.
    """
    sbx = get_sandbox()
    data = _read_bytes(sbx, sandbox_path)
    if not data:
        return f"Could not read {sandbox_path} from the sandbox."

    default_ext, mime = _MIME.get(kind, ("bin", "application/octet-stream"))
    ext = (os.path.splitext(sandbox_path)[1].lstrip(".") or default_ext)
    art = store_bytes(data, kind=kind, mime=mime, ext=ext)

    if db_enabled():
        try:
            from ...models import Artifact

            with session_scope() as session:
                session.add(Artifact(type=kind, uri=art.path, mime=mime,
                                     meta={"source": sandbox_path}))
        except Exception:
            pass

    url = f"/artifacts/{art.id}/download"
    marker = json.dumps({"artifact_id": art.id, "kind": kind, "mime": mime, "url": url})
    return f"Saved {kind} ({len(data)} bytes). Download: {url}\nARTIFACT:{marker}"
