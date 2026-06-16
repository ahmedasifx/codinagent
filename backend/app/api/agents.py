"""Agent/skill/tool read endpoints (registry introspection). Full CRUD lands in P5."""

from fastapi import APIRouter

from ..registries.agent_registry import AGENT_REGISTRY
from ..registries.loader import load_builtins
from ..registries.skill_registry import SKILL_REGISTRY
from ..registries.tool_registry import TOOL_REGISTRY

router = APIRouter()


@router.get("/agents")
async def list_agents():
    load_builtins()
    return [
        {
            "slug": a.slug,
            "name": a.name,
            "description": a.description,
            "skills": a.skills,
            "tools": a.tools,
            "is_core": a.is_core,
        }
        for a in AGENT_REGISTRY.list()
    ]


@router.get("/skills")
async def list_skills():
    load_builtins()
    return [
        {
            "slug": s.slug,
            "name": s.name,
            "description": s.description,
            "when_to_use": s.when_to_use,
            "required_tools": s.required_tools,
            "is_core": s.is_core,
        }
        for s in SKILL_REGISTRY.list()
    ]


@router.get("/tools")
async def list_tools():
    load_builtins()
    return [{"slug": slug} for slug in TOOL_REGISTRY.list_internal()]
