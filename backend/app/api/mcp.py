"""MCP server registration. An MCP server is persisted as a `tools` row of type `mcp`
whose `spec` holds the connection; it then attaches to agents like any other tool."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import db_enabled, get_db
from ..schemas.registry import McpServerIn

router = APIRouter()


def _require_db():
    if not db_enabled():
        raise HTTPException(503, "Database not configured (DB-less mode)")


@router.get("/mcp/servers")
async def list_mcp_servers(db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    rows = db.query(Tool).filter(Tool.type == "mcp").all()
    return [{"id": str(r.id), "slug": r.slug, "name": r.name, "spec": r.spec} for r in rows]


@router.post("/mcp/servers", status_code=201)
async def register_mcp_server(payload: McpServerIn, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    if db.query(Tool).filter(Tool.slug == payload.slug).first():
        raise HTTPException(409, f"Tool '{payload.slug}' already exists")
    row = Tool(
        slug=payload.slug,
        name=payload.name or payload.slug,
        description=payload.description,
        type="mcp",
        spec={
            "server": payload.slug,
            "connection": payload.connection,
            "tool_name": payload.tool_name,
        },
        is_core=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "slug": row.slug, "spec": row.spec}


@router.get("/mcp/servers/{server_id}/tools")
async def list_mcp_tools(server_id: str, db: Session = Depends(get_db)):
    """List the tools exposed by a registered MCP server (requires the optional
    langchain-mcp-adapters package)."""
    _require_db()
    from ..models import Tool

    row = db.get(Tool, uuid.UUID(server_id))
    if not row or row.type != "mcp":
        raise HTTPException(404, "MCP server not found")
    try:
        import asyncio

        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({row.spec["server"]: row.spec["connection"]})
        tools = asyncio.run(client.get_tools())
        return [{"name": t.name, "description": t.description} for t in tools]
    except ImportError:
        raise HTTPException(
            501,
            "MCP support requires `langchain-mcp-adapters` (needs langchain-core>=0.3.36). "
            "Bump the langchain stack and `pip install langchain-mcp-adapters`.",
        )
    except Exception as e:
        raise HTTPException(502, f"Could not connect to MCP server: {e}")
