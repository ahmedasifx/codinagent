"""Document skills — generate professional PDF documents."""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_TOOLS = ["write_file", "read_file", "run_command", "install_package", "execute_python", "save_artifact"]

register_skill(
    SkillDef(
        slug="generate_document",
        name="Generate Document",
        description="Generate a professional PDF (CV, report, proposal, invoice, etc.).",
        when_to_use="create a PDF document such as a CV, report, proposal, invoice, or business doc",
        required_tools=_TOOLS,
        instructions="""Generate a polished PDF end-to-end. Work under /home/user/app/doc.

1. STRUCTURE — decide the document type and outline its sections (e.g. CV: header,
   summary, experience, education, skills). Generate concrete, well-written content.
2. RENDER to PDF in the sandbox. Prefer reportlab for precise layouts or weasyprint for
   HTML/CSS-styled documents:
   - run_command("pip install reportlab -q", cwd="/home/user/app/doc")  (or weasyprint)
   - execute_python to build /home/user/app/doc/out.pdf — use clear typography,
     consistent margins, section headings, and tables where useful.
3. save_artifact("/home/user/app/doc/out.pdf", "pdf") and give the user the download URL
   with a short summary of what you produced.""",
    )
)
