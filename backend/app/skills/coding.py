"""Core coding skills — the original WORKFLOW_PROMPTS expressed as composable Skills."""

from ..registries.skill_registry import register_skill
from ..registries.types import SkillDef

_SANDBOX_TOOLS = [
    "execute_python",
    "install_package",
    "run_command",
    "write_file",
    "read_file",
    "list_files",
    "start_server",
    "stop_server",
]

register_skill(
    SkillDef(
        slug="landing_page",
        name="Landing Page",
        description="Build/modify a landing page, marketing page, portfolio, or static website UI.",
        when_to_use="build/modify a landing page, marketing page, portfolio, or static website UI",
        required_tools=_SANDBOX_TOOLS,
        instructions="""## Current workflow: LANDING PAGE
Build the page as a React + Vite app (unless the user explicitly asks for plain HTML):
1. Scaffold files manually under /home/user/app with write_file — package.json, vite.config.js, index.html, src/main.jsx, src/App.jsx, src/index.css. Do NOT use interactive `npm create vite`.
2. vite.config.js must include `server: { host: true, allowedHosts: true }`.
3. run_command("npm install", cwd="/home/user/app") — this can take a minute.
4. start_server("npm run dev -- --host --port 5173", 5173, cwd="/home/user/app").
5. Report the preview URL. On follow-up feedback, edit the relevant files with write_file — Vite hot-reloads, no restart needed.
Make the page visually polished: real copy, a hero section, sensible color palette, responsive layout.""",
    )
)

register_skill(
    SkillDef(
        slug="fullstack",
        name="Fullstack App",
        description="Build/modify an app with backend logic (API, database, CRUD) plus a frontend.",
        when_to_use="build/modify an app with backend logic (API, database, CRUD) plus a frontend",
        required_tools=_SANDBOX_TOOLS,
        instructions="""## Current workflow: FULLSTACK APP
Build a FastAPI backend that serves BOTH the API and the static frontend on ONE port (no CORS, no second server):
1. Scaffold under /home/user/app: main.py (FastAPI with API routes + StaticFiles mount at "/") and a static/ dir with index.html, style.css, app.js that call the API with fetch().
2. run_command("pip install fastapi uvicorn", cwd="/home/user/app") if needed.
3. Test API endpoints with run_command using curl against localhost BEFORE exposing the preview.
4. start_server("uvicorn main:app --host 0.0.0.0 --port 8000", 8000, cwd="/home/user/app").
5. Report the preview URL and summarize the API endpoints.""",
    )
)

register_skill(
    SkillDef(
        slug="general",
        name="General Coding",
        description="Scripts, data analysis, algorithms, questions, charts.",
        when_to_use="everything else (scripts, data analysis, algorithms, questions, charts)",
        required_tools=_SANDBOX_TOOLS,
        instructions="",
    )
)
