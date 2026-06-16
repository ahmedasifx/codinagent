"""P0 smoke tests: registries populate, graph compiles, skill->tool resolution works.

Run: ./venv/bin/python -m pytest -q   (pytest is optional; see test_foundation_main)
"""

from app.registries.agent_registry import AGENT_REGISTRY
from app.registries.loader import load_builtins
from app.registries.skill_registry import SKILL_REGISTRY
from app.registries.tool_registry import TOOL_REGISTRY


def test_builtins_register():
    load_builtins()
    assert AGENT_REGISTRY.get("coding_agent").slug == "coding_agent"
    assert {"landing_page", "fullstack", "general"} <= {
        s.slug for s in SKILL_REGISTRY.list()
    }
    assert "execute_python" in TOOL_REGISTRY.list_internal()


def test_tool_resolution():
    load_builtins()
    skill = SKILL_REGISTRY.get("landing_page")
    tools = TOOL_REGISTRY.resolve(skill.required_tools)
    assert len(tools) == len(skill.required_tools)
    assert all(hasattr(t, "invoke") for t in tools)


def test_graph_compiles():
    load_builtins()
    graph = AGENT_REGISTRY.compiled_graph("coding_agent")
    assert graph is not None


def test_unknown_agent_raises():
    load_builtins()
    try:
        AGENT_REGISTRY.get("does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


if __name__ == "__main__":
    test_builtins_register()
    test_tool_resolution()
    test_graph_compiles()
    test_unknown_agent_raises()
    print("P0 foundation tests passed")
