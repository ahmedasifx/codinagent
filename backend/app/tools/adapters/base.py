"""Uniform tool adapter interface — the seam that lets *any* skill use *any* tool.

Every tool type (internal Python fn, REST API, MCP server, ...) is wrapped by an
adapter exposing `to_langchain_tool()`, which returns a LangChain tool the LLM can
bind. The ToolRegistry deals only in adapters, so callers never branch on tool type.
"""

from abc import ABC, abstractmethod

from langchain_core.tools import BaseTool


class ToolAdapter(ABC):
    slug: str
    description: str

    @abstractmethod
    def to_langchain_tool(self) -> BaseTool:  # pragma: no cover - interface
        ...


class InternalToolAdapter(ToolAdapter):
    """Wraps an already-decorated LangChain `@tool` function (the built-in tools)."""

    def __init__(self, tool: BaseTool) -> None:
        self._tool = tool
        self.slug = tool.name
        self.description = tool.description or ""

    def to_langchain_tool(self) -> BaseTool:
        return self._tool
