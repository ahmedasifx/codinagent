"""Text-to-speech tool (optional voiceover).

Uses an OpenAI-compatible audio/speech endpoint when TTS_API_KEY + TTS_BASE_URL are
configured; otherwise returns a clear, non-fatal message so videos can render silently.
Writes the audio into the sandbox so Remotion can <Audio> it.
"""

import os

import httpx
from langchain_core.tools import tool

from ...core.sandbox import get_sandbox
from ...registries.tool_registry import register_tool


@register_tool
@tool
def tts(text: str, out_path: str, voice: str = "alloy") -> str:
    """Synthesize speech from text and write an mp3 into the sandbox at out_path.

    Use for voiceover/narration. If TTS is not configured this returns a notice and you
    should proceed without audio (render a silent video).
    """
    api_key = os.environ.get("TTS_API_KEY", "")
    base_url = os.environ.get("TTS_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("TTS_MODEL", "tts-1")
    if not api_key:
        return (
            "TTS not configured (set TTS_API_KEY / TTS_BASE_URL / TTS_MODEL). "
            "Proceed without voiceover — render a silent video."
        )
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "voice": voice, "input": text},
            timeout=120,
        )
        resp.raise_for_status()
        get_sandbox().files.write(out_path, resp.content)
        return f"Wrote {len(resp.content)} bytes of audio to {out_path}"
    except Exception as e:
        return f"TTS failed: {e}. Proceed without voiceover."
