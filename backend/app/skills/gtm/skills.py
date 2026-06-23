"""GTM skills — positioning/messaging → outreach sequences → GTM plan PDF.

Granular skills plus one composite (`build_gtm`). The PDF is rendered in-agent (reusing
the document agent's reportlab/weasyprint recipe) rather than by delegating, so the
artifact stays in this run's tool output.
"""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_DOC_TOOLS = ["write_file", "read_file", "run_command", "install_package", "execute_python", "save_artifact"]
_PROJECT = "/home/user/app/gtm"

register_skill(
    SkillDef(
        slug="positioning_messaging",
        name="Positioning & Messaging",
        description="Define positioning, value props, and objection handling for the ICP.",
        when_to_use="craft positioning/messaging for a product and its target buyers",
        required_tools=["write_file"],
        instructions=f"""Produce positioning + messaging and write {_PROJECT}/messaging.json:
{{ "positioning_statement": str, "category": str, "differentiators": [...],
  "value_props": [ {{ "persona": str, "headline": str, "proof_points": [...] }} ],
  "objections": [ {{ "objection": str, "response": str }} ],
  "tone": str }}
Ground it in the target ICP/personas. Be concrete and benefit-led, not generic.""",
    )
)

register_skill(
    SkillDef(
        slug="outreach_sequences",
        name="Outreach Sequences",
        description="Write multi-touch email/LinkedIn outreach sequences per segment.",
        when_to_use="create cold outreach email/LinkedIn sequences for prospects",
        required_tools=["write_file", "read_file"],
        instructions=f"""Read {_PROJECT}/messaging.json (if present). Write a 3–5 touch
sequence per buyer persona to {_PROJECT}/sequences.md: for each touch give channel
(email/LinkedIn), day offset, subject line (email), and a short personalized body using
the value props and proof points. Keep emails <120 words, one clear CTA each, no spammy
language. Output the sequences clearly so the user can copy them directly.""",
    )
)

register_skill(
    SkillDef(
        slug="gtm_plan_doc",
        name="GTM Plan Document",
        description="Render a go-to-market plan as a polished PDF.",
        when_to_use="produce a downloadable GTM plan/strategy document",
        required_tools=_DOC_TOOLS,
        instructions=f"""Assemble a GTM plan PDF end-to-end under {_PROJECT}. Pull in the
ICP, positioning/messaging, and outreach sequences produced earlier (read the JSON/MD
files if present). Sections: Executive summary, Target market & ICP, Positioning &
messaging, Channel strategy, Outreach plan (summarize the sequences), Metrics & targets,
30/60/90-day rollout.
Render with reportlab or weasyprint (HTML/CSS):
- run_command("pip install weasyprint -q", cwd="{_PROJECT}")   (or reportlab)
- execute_python to build {_PROJECT}/gtm_plan.pdf with clear headings, consistent
  margins, and tables for the rollout/metrics.
Then save_artifact("{_PROJECT}/gtm_plan.pdf", "pdf") and give the download URL.""",
    )
)

# ── Composite (entry) skill ──
register_skill(
    SkillDef(
        slug="build_gtm",
        name="Build GTM Strategy",
        description="End-to-end GTM: positioning → outreach sequences → plan PDF.",
        when_to_use="any request for a go-to-market plan/strategy, positioning, or outreach campaign",
        required_tools=_DOC_TOOLS,
        sub_skills=["positioning_messaging", "outreach_sequences", "gtm_plan_doc"],
        instructions=f"""Build a go-to-market package end-to-end. Work under {_PROJECT}.

1. POSITIONING — write messaging.json (positioning, differentiators, per-persona value
   props, objection handling, tone) grounded in the target ICP.
2. OUTREACH — write sequences.md: a 3–5 touch email/LinkedIn sequence per persona, each
   touch with channel, day offset, subject, and a short personalized body (<120 words,
   one CTA). Output them so the user can copy directly.
3. PLAN PDF — assemble gtm_plan.pdf (exec summary, ICP, positioning, channel strategy,
   outreach plan, metrics, 30/60/90-day rollout) with weasyprint/reportlab, then
   save_artifact(".../gtm_plan.pdf", "pdf").

Finish with the PDF download URL and a short recap. Keep everything specific to the
product and buyers described — avoid generic boilerplate.""",
    )
)
