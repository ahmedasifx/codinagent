"""Lead Generation skills (web-search sourcing → enrichment → scoring → export).

Granular, reusable skills plus one composite (`generate_leads`) that orchestrates the
full pipeline. The agent selects the composite; the granular skills are registered for
composition/reuse and listed as `sub_skills`. Mirrors the infographic_video pattern.
"""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_SOURCE_TOOLS = ["web_search", "fetch_url", "scrape_page", "crawl_site", "write_file", "read_file"]
_BUILD_TOOLS = ["execute_python", "write_file", "read_file", "list_files", "install_package"]
_ALL_TOOLS = list(dict.fromkeys(
    _SOURCE_TOOLS + _BUILD_TOOLS + ["save_artifact", "start_server", "stop_server"]
))
_PROJECT = "/home/user/app/leads"

register_skill(
    SkillDef(
        slug="icp_definition",
        name="ICP Definition",
        description="Derive an Ideal Customer Profile from the request.",
        when_to_use="define the target customer profile before sourcing prospects",
        required_tools=["write_file"],
        instructions=f"""Derive a concrete Ideal Customer Profile (ICP) from the user's
request and write it to {_PROJECT}/icp.json:
{{ "firmographics": {{ "industry": [...], "company_size": str, "geography": [...],
   "funding_stage": str|null }},
  "buyer_personas": [ {{ "title": str, "seniority": str, "pain_points": [...] }} ],
  "buying_signals": [...],            // e.g. hiring, recent funding, tech adoption
  "disqualifiers": [...],
  "scoring_weights": {{ "industry_fit": 0.3, "size_fit": 0.2, "title_fit": 0.3,
   "signal_strength": 0.2 }} }}
Be specific — these weights drive scoring later.""",
    )
)

register_skill(
    SkillDef(
        slug="prospect_sourcing",
        name="Prospect Sourcing",
        description="Find companies/contacts matching the ICP via web search.",
        when_to_use="find candidate companies and contacts that match the ICP",
        required_tools=_SOURCE_TOOLS,
        instructions=f"""Read {_PROJECT}/icp.json. Use web_search with several targeted
queries (industry + geography + signals, e.g. "Series A fintech startups UK 2024",
"<industry> companies hiring <role>"). To read a promising result, prefer scrape_page
(real browser, renders JS — works on modern SaaS sites where fetch_url returns an empty
shell); use fetch_url only for simple static pages. Collect 10–25 candidate companies.
Write {_PROJECT}/prospects_raw.json as a list of:
{{ "company": str, "website": str, "source_url": str, "notes": str }}
Cite the source_url for every prospect — do not invent companies.""",
    )
)

register_skill(
    SkillDef(
        slug="lead_enrichment",
        name="Lead Enrichment",
        description="Enrich each prospect with firmographics + contact hints.",
        when_to_use="add company size, industry, tech, and contact details to prospects",
        required_tools=_SOURCE_TOOLS,
        instructions=f"""Read {_PROJECT}/prospects_raw.json. For each prospect, gather its
public pages — use crawl_site(website, max_pages=5) to pull about/team/pricing/contact in
one call (JS rendered), or scrape_page for a single page. From the returned markdown
extract: industry, approx company size, location, notable tech/products, and any public
contact (role + name or generic email pattern). Write {_PROJECT}/prospects_enriched.json
adding these fields. If a fact isn't found, set it to null — never fabricate emails or
names.""",
    )
)

register_skill(
    SkillDef(
        slug="lead_scoring",
        name="Lead Scoring",
        description="Score and rank enriched prospects against the ICP.",
        when_to_use="score/rank prospects by fit against the ICP",
        required_tools=_BUILD_TOOLS,
        instructions=f"""With execute_python, load {_PROJECT}/icp.json and
{_PROJECT}/prospects_enriched.json into pandas. Compute a 0–100 fit score per prospect
using the ICP scoring_weights (industry_fit, size_fit, title_fit, signal_strength),
apply disqualifiers (score 0 / flag), sort descending, and write
{_PROJECT}/leads_scored.json (and keep the DataFrame for export). Print the top 5 with
scores so the user sees a preview.""",
    )
)

register_skill(
    SkillDef(
        slug="list_export",
        name="Lead List Export",
        description="Export the scored leads as a downloadable CSV.",
        when_to_use="produce the final downloadable lead list",
        required_tools=_BUILD_TOOLS + ["save_artifact"],
        instructions=f"""With execute_python, write the scored leads to
{_PROJECT}/leads.csv (columns: rank, company, website, industry, size, location,
contact, score, signals, source_url). Then call
save_artifact("{_PROJECT}/leads.csv", "csv") and give the user the download URL plus a
short summary (count, score range, top accounts).""",
    )
)

register_skill(
    SkillDef(
        slug="lead_dashboard",
        name="Lead Dashboard",
        description="Serve a small live dashboard of the lead list.",
        when_to_use="show an interactive/live view of the lead list",
        required_tools=["write_file", "read_file", "start_server", "stop_server"],
        instructions=f"""Optional. Build a single static index.html under
{_PROJECT}/dashboard that reads leads (inline the JSON/CSV data into the page) and
renders a sortable table + a simple score histogram (vanilla JS or a CDN chart lib).
Then start_server("python3 -m http.server 8080", 8080, cwd="{_PROJECT}/dashboard") and
report the PREVIEW_URL.""",
    )
)

# ── Composite (entry) skill ──
register_skill(
    SkillDef(
        slug="generate_leads",
        name="Generate Leads",
        description="End-to-end lead generation: ICP → source → enrich → score → CSV.",
        when_to_use="any request to find, build, or generate a list of sales leads/prospects",
        required_tools=_ALL_TOOLS,
        sub_skills=[
            "icp_definition",
            "prospect_sourcing",
            "lead_enrichment",
            "lead_scoring",
            "list_export",
            "lead_dashboard",
        ],
        instructions=f"""Generate a scored lead list end-to-end. Work under {_PROJECT}.
Execute the pipeline in order:

1. ICP — write icp.json (firmographics, buyer personas, buying signals, disqualifiers,
   scoring_weights) from the user's request.
2. SOURCE — web_search to discover, then scrape_page (JS-rendered; fetch_url only for
   static pages) to confirm 10–25 real companies matching the ICP; write prospects_raw.json
   with a source_url for each (never invent companies).
3. ENRICH — crawl_site(website) (or scrape_page) for industry, size, location, tech,
   contact hints; write prospects_enriched.json (null for anything not found — no
   fabricated emails).
4. SCORE — execute_python + pandas to score 0–100 against the ICP weights, apply
   disqualifiers, rank; write leads_scored.json and print the top 5.
5. EXPORT — write leads.csv and save_artifact(".../leads.csv", "csv"); give the
   download URL + a summary.
6. DASHBOARD (optional) — if the user wants a live view, build dashboard/index.html and
   start_server; report the preview URL.

Be rigorous about provenance: every lead must trace to a real source_url. Prefer fewer
high-quality, verifiable leads over a long fabricated list.""",
    )
)
