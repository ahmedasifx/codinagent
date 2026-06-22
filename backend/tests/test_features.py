"""P1/P2/P5 feature tests — hermetic (DB only, no LLM/sandbox calls).

Run against the dockerized Postgres:
  DATABASE_URL=postgresql://agent:agent@localhost:5433/agent \
  PYTHONPATH=. ./venv/bin/python tests/test_features.py
"""

import os
import uuid

assert os.environ.get("DATABASE_URL"), "set DATABASE_URL to a live Postgres for these tests"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
sfx = uuid.uuid4().hex[:8]


def test_tool_crud():
    slug = f"httpbin_get_{sfx}"
    r = client.post("/tools", json={
        "slug": slug, "name": "Httpbin GET", "type": "rest_api",
        "spec": {"base_url": "https://httpbin.org", "method": "GET", "path": "/get",
                 "params": {"q": {"type": "string", "in": "query"}},
                 "allowlist": ["httpbin.org"]},
    })
    assert r.status_code == 201, r.text
    tool_id = r.json()["id"]
    assert any(t["slug"] == slug for t in client.get("/tools").json())
    assert client.get(f"/tools/{tool_id}").json()["slug"] == slug
    assert client.put(f"/tools/{tool_id}", json={"description": "updated"}).json()["description"] == "updated"
    assert client.delete(f"/tools/{tool_id}").status_code == 204
    print("✓ tool CRUD")


def test_credentials_crud():
    r = client.post("/credentials", json={"name": f"cred_{sfx}", "type": "bearer", "secret_ref": "SOME_ENV"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert any(c["id"] == cid for c in client.get("/credentials").json())
    assert client.delete(f"/credentials/{cid}").status_code == 204
    print("✓ credentials CRUD")


def test_mcp_register():
    slug = f"mcp_{sfx}"
    r = client.post("/mcp/servers", json={
        "slug": slug, "name": "Demo MCP",
        "connection": {"transport": "streamable_http", "url": "https://example.com/mcp"},
    })
    assert r.status_code == 201, r.text
    assert any(s["slug"] == slug for s in client.get("/mcp/servers").json())
    print("✓ MCP register")


def test_memory_save_recall():
    from app.memory import store

    ns = f"test_{sfx}"
    assert store.save("The launch date is March 14", namespace=ns)
    hits = store.recall("launch", k=3, namespace=ns)
    assert any("March 14" in h for h in hits), hits
    print("✓ memory save→recall")


def test_custom_agent_create_and_compile():
    from app.registries.agent_registry import AGENT_REGISTRY

    slug = f"my_agent_{sfx}"
    r = client.post("/agents", json={
        "slug": slug, "name": "My Agent", "system_prompt": "You are helpful.",
        "skills": ["general"], "tools": ["execute_python", "recall_memory"],
        "config": {"auto_recall": True},
    })
    assert r.status_code == 201, r.text
    assert any(a["slug"] == slug for a in client.get("/agents").json())
    # registry loads it from DB and the engine compiles a graph
    AGENT_REGISTRY.invalidate(slug)
    agent = AGENT_REGISTRY.get(slug)
    assert agent.skills == ["general"] and "recall_memory" in agent.tools
    assert AGENT_REGISTRY.compiled_graph(slug) is not None
    assert client.delete(f"/agents/{slug}").status_code == 204
    print("✓ custom agent create + compile")


def test_orchestration_tool_registered():
    from app.registries.loader import load_builtins
    from app.registries.tool_registry import TOOL_REGISTRY

    load_builtins()
    assert TOOL_REGISTRY.has("delegate_to_agent")
    print("✓ delegate_to_agent registered")


def test_resolve_planning_mode():
    from app.engine.planner import resolve_planning_mode

    # approved_plan always forces execute
    assert resolve_planning_mode("auto", {"planning": "approve"}, "a plan") == "execute"
    # explicit request wins over config
    assert resolve_planning_mode("approve", {"planning": "off"}, None) == "approve"
    # falls back to agent config
    assert resolve_planning_mode(None, {"planning": "auto"}, None) == "auto"
    # default off
    assert resolve_planning_mode(None, {}, None) == "off"
    assert resolve_planning_mode("garbage", None, None) == "off"
    print("✓ resolve_planning_mode")


def test_invoke_with_retry():
    from app.engine import planner

    class Boom(Exception):
        pass

    # transient: fails twice (429) then succeeds
    calls = {"n": 0}

    class StubLLM:
        def invoke(self, _msgs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise Boom("Provider returned error 429")
            return "ok"

    # speed up backoff
    import time as _t
    orig = _t.sleep
    _t.sleep = lambda *_: None
    try:
        assert planner._invoke_with_retry(StubLLM(), [], attempts=4) == "ok"
        assert calls["n"] == 3

        # non-transient: raises immediately, no retries
        hits = {"n": 0}

        class HardFail:
            def invoke(self, _msgs):
                hits["n"] += 1
                raise Boom("invalid request: bad schema")

        try:
            planner._invoke_with_retry(HardFail(), [], attempts=4)
            assert False, "expected raise"
        except Boom:
            assert hits["n"] == 1
    finally:
        _t.sleep = orig
    print("✓ _invoke_with_retry")


def test_planning_failure_emits_error_not_plan():
    """approve-mode planning failure → error event, NO plan/awaiting_approval."""
    import asyncio

    from app.engine import planner, runner

    orig = planner.generate_plan

    def boom(*a, **k):
        raise RuntimeError("Provider returned error 429")

    # runner imports generate_plan inside the function from .planner, so patch there
    planner.generate_plan = boom
    try:
        async def collect():
            evs = []
            async for e in runner.run_agent_stream(
                "hi", [], agent_slug="coding_agent", planning="approve"
            ):
                evs.append(e["type"])
            return evs

        types = asyncio.run(collect())
    finally:
        planner.generate_plan = orig

    assert "error" in types, types
    assert "plan" not in types and "awaiting_approval" not in types, types
    print("✓ planning failure → error (no fake plan)")


def test_remotion_blank_heuristic():
    from app.tools.internal.remotion import _looks_blank

    assert _looks_blank(8.0, 1.2) is True      # flat + static → blank
    assert _looks_blank(40.0, 9.0) is False     # detailed + moving → fine
    assert _looks_blank(40.0, 1.0) is False     # detailed but static → not flagged
    print("✓ remotion blank heuristic")


def test_plan_injected_into_prompt():
    from app.engine.context import assemble_system_prompt
    from app.registries.types import AgentDef

    a = AgentDef(slug="x", name="X", description="", system_prompt="You are X.")
    out = assemble_system_prompt(a, None, None, plan="1. do a thing")
    assert "Approved plan" in out and "do a thing" in out
    print("✓ plan injected into system prompt")


if __name__ == "__main__":
    test_tool_crud()
    test_credentials_crud()
    test_mcp_register()
    test_memory_save_recall()
    test_custom_agent_create_and_compile()
    test_orchestration_tool_registered()
    test_resolve_planning_mode()
    test_invoke_with_retry()
    test_planning_failure_emits_error_not_plan()
    test_remotion_blank_heuristic()
    test_plan_injected_into_prompt()
    print("\nAll feature tests passed")
