"""Skill registry — code-defined built-in skills + DB-defined custom skills."""

from .types import SkillDef


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDef] = {}

    def register(self, skill: SkillDef) -> SkillDef:
        self._skills[skill.slug] = skill
        return skill

    def get(self, slug: str) -> SkillDef:
        if slug in self._skills:
            return self._skills[slug]
        custom = self._load_custom(slug)
        if custom is None:
            raise KeyError(f"Unknown skill: {slug}")
        return custom

    def get_many(self, slugs: list[str]) -> list[SkillDef]:
        out: list[SkillDef] = []
        for slug in slugs:
            try:
                out.append(self.get(slug))
            except KeyError:
                continue
        return out

    def list(self) -> list[SkillDef]:
        return list(self._skills.values())

    def _load_custom(self, slug: str) -> SkillDef | None:
        from ..core.db import db_enabled, session_scope

        if not db_enabled():
            return None
        from ..models import Skill

        with session_scope() as session:
            row = session.query(Skill).filter(Skill.slug == slug).one_or_none()
            if row is None:
                return None
            cfg = row.config or {}
            return SkillDef(
                slug=row.slug,
                name=row.name,
                description=row.description,
                instructions=row.instructions,
                when_to_use=row.when_to_use,
                # slugs (core or custom) stored in config — no FK constraint
                required_tools=cfg.get("required_tools", []),
                sub_skills=cfg.get("sub_skills", []),
                is_core=False,
            )


SKILL_REGISTRY = SkillRegistry()


def register_skill(skill: SkillDef) -> SkillDef:
    return SKILL_REGISTRY.register(skill)
