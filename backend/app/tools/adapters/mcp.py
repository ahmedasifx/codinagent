"""MCP tool adapter (Model Context Protocol).

Wraps tools exposed by an MCP server using `langchain-mcp-adapters`. A `tools` row of
type `mcp` carries the server connection in `spec`:

spec = {
  "server": "my_server",
  "connection": {"transport": "stdio", "command": "npx", "args": ["-y", "some-mcp"]}
                or {"transport": "streamable_http", "url": "https://host/mcp"},
  "tool_name": "specific_tool"   # optional: expose just one of the server's tools
}

The langchain-mcp-adapters import is deferred to call time so this module imports
cleanly even when the optional dependency isn't installed.
"""

from langchain_core.tools import BaseTool, StructuredTool

from .base import ToolAdapter


class McpToolAdapter(ToolAdapter):
    def __init__(self, slug: str, description: str, spec: dict) -> None:
        self.slug = slug
        self.description = description
        self.spec = spec

    @classmethod
    def from_row(cls, row) -> "McpToolAdapter":
        return cls(row.slug, row.description or "", row.spec or {})

    def to_langchain_tool(self) -> BaseTool:
        spec = self.spec
        server = spec.get("server", self.slug)
        connection = spec.get("connection", {})
        want = spec.get("tool_name")

        async def _load() -> list[BaseTool]:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            client = MultiServerMCPClient({server: connection})
            return await client.get_tools()

        def _call(**kwargs) -> str:
            import asyncio

            tools = asyncio.run(_load())
            target = next(
                (t for t in tools if not want or t.name == want), tools[0] if tools else None
            )
            if target is None:
                return f"MCP server '{server}' exposed no tools."
            return str(target.invoke(kwargs))

        return StructuredTool.from_function(
            func=_call, name=self.slug, description=self.description or f"MCP tool {self.slug}"
        )
