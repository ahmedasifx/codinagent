"""Compatibility shim for the original monolith.

The coding agent has been decomposed into the `app/` package:
  - tools         → app/tools/internal/sandbox.py
  - sandbox       → app/core/sandbox.py
  - LLM access    → app/engine/llm.py
  - graph/runner  → app/engine/graph.py, app/engine/runner.py
  - prompts       → app/skills/coding.py + app/agents/coding_agent.py

These re-exports keep older imports (`from agent import ...`) working.
"""

from app.core.sandbox import close_sandbox, get_sandbox  # noqa: F401
from app.engine.runner import run_agent_stream  # noqa: F401
