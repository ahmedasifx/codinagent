"""Adapter factory: build a ToolAdapter from a DB `tools` row by its `type`.

P0 supports `internal` (alias to a built-in). REST/MCP adapters are added in P1.
"""

from .base import ToolAdapter


def build_adapter_for_row(row) -> ToolAdapter | None:
    if row.type == "internal":
        # An `internal` custom row just points at a built-in by slug (spec.target).
        from ...registries.tool_registry import TOOL_REGISTRY

        target = row.spec.get("target", row.slug)
        if TOOL_REGISTRY.has(target):
            return TOOL_REGISTRY.adapter(target)
        return None

    if row.type in ("rest_api", "external"):
        from .rest import RestApiToolAdapter

        return RestApiToolAdapter.from_row(row)

    if row.type == "mcp":
        from .mcp import McpToolAdapter

        return McpToolAdapter.from_row(row)

    return None
