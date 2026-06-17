"""Tool registry CRUD + dry-run test. Built-in tools are read-only; custom tools
(REST/MCP/external/internal-alias) are persisted in the `tools` table."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import db_enabled, get_db
from ..registries.loader import load_builtins
from ..registries.tool_registry import TOOL_REGISTRY
from ..schemas.registry import ToolIn, ToolOut, ToolTestIn, ToolUpdate

router = APIRouter()


def _require_db():
    if not db_enabled():
        raise HTTPException(503, "Database not configured (DB-less mode)")


def _row_out(row) -> ToolOut:
    return ToolOut(
        id=str(row.id), slug=row.slug, name=row.name, description=row.description,
        type=row.type, spec=row.spec, is_core=row.is_core,
    )


@router.get("/tools")
async def list_tools(db: Session = Depends(get_db)):
    load_builtins()
    out: list[ToolOut] = [
        ToolOut(slug=s, name=s, type="internal", is_core=True)
        for s in TOOL_REGISTRY.list_internal()
    ]
    if db_enabled():
        from ..models import Tool

        for row in db.query(Tool).all():
            out.append(_row_out(row))
    return out


@router.post("/tools", status_code=201)
async def create_tool(payload: ToolIn, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    if db.query(Tool).filter(Tool.slug == payload.slug).first():
        raise HTTPException(409, f"Tool '{payload.slug}' already exists")
    row = Tool(
        slug=payload.slug, name=payload.name, description=payload.description,
        type=payload.type, spec=payload.spec,
        credential_id=uuid.UUID(payload.credential_id) if payload.credential_id else None,
        is_core=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_out(row)


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    row = db.get(Tool, uuid.UUID(tool_id))
    if not row:
        raise HTTPException(404, "Tool not found")
    return _row_out(row)


@router.put("/tools/{tool_id}")
async def update_tool(tool_id: str, payload: ToolUpdate, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    row = db.get(Tool, uuid.UUID(tool_id))
    if not row:
        raise HTTPException(404, "Tool not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "credential_id" and value:
            value = uuid.UUID(value)
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _row_out(row)


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: str, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Tool

    row = db.get(Tool, uuid.UUID(tool_id))
    if row:
        db.delete(row)
        db.commit()


@router.post("/tools/{slug}/test")
async def test_tool(slug: str, payload: ToolTestIn):
    """Dry-run a tool (built-in or custom) with sample args."""
    load_builtins()
    try:
        tool = TOOL_REGISTRY.get_langchain_tool(slug)
    except KeyError:
        raise HTTPException(404, f"Unknown tool: {slug}")
    try:
        result = tool.invoke(payload.args)
        return {"ok": True, "result": str(result)[:4000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
