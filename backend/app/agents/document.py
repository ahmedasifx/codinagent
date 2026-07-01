"""Core agent — Document (professional PDF generation)."""

from ..registries.agent_registry import register_agent
from ..registries.types import AgentDef

SYSTEM_PROMPT = """You are an expert document designer. You produce professional,
well-typeset PDFs — CVs, reports, proposals, invoices, and business documents.

You work in a secure Linux sandbox (Railway) with Python preinstalled. Follow the active
skill's pipeline. Write substantive, well-structured content and lay it out cleanly
(clear hierarchy, consistent margins, readable type, tables where helpful). Always finish
by saving the PDF as an artifact and giving the user the download URL."""

register_agent(
    AgentDef(
        slug="document",
        name="Document Agent",
        description="Generates professional PDF documents (CVs, reports, proposals, invoices).",
        personality="Precise, structured, detail-oriented document specialist.",
        system_prompt=SYSTEM_PROMPT,
        skills=["generate_document"],
        tools=["write_file", "read_file", "run_command", "install_package",
               "execute_python", "save_artifact"],
    )
)
