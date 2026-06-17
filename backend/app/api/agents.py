"""Agent + skill registry endpoints: list (core + custom) and no-code CRUD for
custom agents/skills. Skill/tool membership is stored as slug lists in `config` so a
custom agent can mix core (code-defined) and custom (DB) skills/tools freely."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import db_enabled, get_db
from ..registries.agent_registry import AGENT_REGISTRY
from ..registries.loader import load_builtins
from ..registries.skill_registry import SKILL_REGISTRY
from ..schemas.registry import AgentIn, AgentUpdate, SkillIn

router = APIRouter()


def _require_db():
    if not db_enabled():
        raise HTTPException(503, "Database not configured (DB-less mode)")


# ── Agents ──────────────────────────────────────────────────────────────────────
@router.get("/agents")
async def list_agents(db: Session = Depends(get_db)):
    load_builtins()
    out = [
        {"slug": a.slug, "name": a.name, "description": a.description,
         "skills": a.skills, "tools": a.tools,
         "planning": a.config.get("planning", "off"), "is_core": True}
        for a in AGENT_REGISTRY.list()
    ]
    core_slugs = {a["slug"] for a in out}
    if db_enabled():
        from ..models import Agent

        for row in db.query(Agent).filter(Agent.is_core == False).all():  # noqa: E712
            if row.slug in core_slugs:
                continue
            cfg = row.config or {}
            out.append({"id": str(row.id), "slug": row.slug, "name": row.name,
                        "description": row.description, "skills": cfg.get("skills", []),
                        "tools": cfg.get("tools", []),
                        "planning": cfg.get("planning", "off"), "is_core": False})
    return out


@router.post("/agents", status_code=201)
async def create_agent(payload: AgentIn, db: Session = Depends(get_db)):
    _require_db()
    load_builtins()
    from ..models import Agent

    if payload.slug in {a.slug for a in AGENT_REGISTRY.list()}:
        raise HTTPException(409, f"'{payload.slug}' is a reserved core agent slug")
    if db.query(Agent).filter(Agent.slug == payload.slug).first():
        raise HTTPException(409, f"Agent '{payload.slug}' already exists")
    cfg = dict(payload.config)
    cfg["skills"], cfg["tools"] = payload.skills, payload.tools
    row = Agent(
        slug=payload.slug, name=payload.name, description=payload.description,
        instructions=payload.instructions, personality=payload.personality,
        system_prompt=payload.system_prompt, model=payload.model, config=cfg, is_core=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "slug": row.slug, "name": row.name,
            "skills": payload.skills, "tools": payload.tools, "is_core": False}


@router.put("/agents/{slug}")
async def update_agent(slug: str, payload: AgentUpdate, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Agent

    row = db.query(Agent).filter(Agent.slug == slug).first()
    if not row:
        raise HTTPException(404, "Custom agent not found")
    data = payload.model_dump(exclude_unset=True)
    cfg = dict(row.config or {})
    for key in ("skills", "tools", "config"):
        if key in data:
            if key == "config":
                cfg.update(data["config"])
            else:
                cfg[key] = data[key]
    row.config = cfg
    for field in ("name", "description", "instructions", "personality", "system_prompt", "model"):
        if field in data:
            setattr(row, field, data[field])
    db.commit()
    AGENT_REGISTRY.invalidate(slug)
    return {"slug": row.slug, "skills": cfg.get("skills", []), "tools": cfg.get("tools", [])}


@router.delete("/agents/{slug}", status_code=204)
async def delete_agent(slug: str, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Agent

    row = db.query(Agent).filter(Agent.slug == slug).first()
    if row:
        db.delete(row)
        db.commit()
        AGENT_REGISTRY.invalidate(slug)


# ── Skills ──────────────────────────────────────────────────────────────────────
@router.get("/skills")
async def list_skills(db: Session = Depends(get_db)):
    load_builtins()
    out = [
        {"slug": s.slug, "name": s.name, "description": s.description,
         "when_to_use": s.when_to_use, "required_tools": s.required_tools, "is_core": True}
        for s in SKILL_REGISTRY.list()
    ]
    core_slugs = {s["slug"] for s in out}
    if db_enabled():
        from ..models import Skill

        for row in db.query(Skill).filter(Skill.is_core == False).all():  # noqa: E712
            if row.slug in core_slugs:
                continue
            cfg = row.config or {}
            out.append({"id": str(row.id), "slug": row.slug, "name": row.name,
                        "description": row.description, "when_to_use": row.when_to_use,
                        "required_tools": cfg.get("required_tools", []), "is_core": False})
    return out


@router.post("/skills", status_code=201)
async def create_skill(payload: SkillIn, db: Session = Depends(get_db)):
    _require_db()
    load_builtins()
    from ..models import Skill

    if payload.slug in {s.slug for s in SKILL_REGISTRY.list()}:
        raise HTTPException(409, f"'{payload.slug}' is a reserved core skill slug")
    if db.query(Skill).filter(Skill.slug == payload.slug).first():
        raise HTTPException(409, f"Skill '{payload.slug}' already exists")
    row = Skill(
        slug=payload.slug, name=payload.name, description=payload.description,
        instructions=payload.instructions, when_to_use=payload.when_to_use, kind="config",
        config={"required_tools": payload.required_tools, "sub_skills": payload.sub_skills},
        is_core=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "slug": row.slug, "name": row.name}


@router.delete("/skills/{slug}", status_code=204)
async def delete_skill(slug: str, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Skill

    row = db.query(Skill).filter(Skill.slug == slug).first()
    if row:
        db.delete(row)
        db.commit()
