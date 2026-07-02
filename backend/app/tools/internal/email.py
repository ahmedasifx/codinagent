"""Email-domain verification tool.

Verifies that a domain can receive mail (MX lookup via dnspython). Pattern inference
(first.last@domain etc.) is left to the LLM per the skill instructions; this tool only
answers "is this domain deliverable at all". No SMTP RCPT probing — that is flaky,
widely blocked, and abusive at scale.

Degrades gracefully in the codebase's style: errors return actionable strings, never raise.
"""

from langchain_core.tools import tool

from ...core import cache
from ...registries.tool_registry import register_tool

_TTL = 7 * 86400  # MX records are stable; cache a week


@register_tool
@tool
def verify_email_domain(domain: str) -> str:
    """Check whether a domain has MX records (i.e. can receive email at all).

    Use before emitting any pattern-inferred contact email: if the domain has no MX,
    set the contact to null. This verifies the DOMAIN only — it cannot confirm that a
    specific mailbox exists, so inferred addresses must stay labeled 'pattern-inferred'.
    """
    domain = domain.strip().lower().removeprefix("http://").removeprefix("https://")
    domain = domain.split("/")[0].removeprefix("www.")
    if "." not in domain:
        return f"'{domain}' is not a valid domain."

    key = f"mx:{domain}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        import dns.resolver
    except ImportError:
        return (
            "Email verification is not available: the 'dnspython' package is not "
            "installed in the backend."
        )

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        hosts = sorted(
            (r.preference, str(r.exchange).rstrip(".")) for r in answers
        )
        listing = ", ".join(h for _, h in hosts[:5])
        out = (
            f"{domain}: MX OK — mail is deliverable to this domain "
            f"(mail hosts: {listing}). Inferred addresses remain unverified guesses."
        )
    except dns.resolver.NXDOMAIN:
        out = f"{domain}: domain does not exist (NXDOMAIN) — do not emit emails for it."
    except dns.resolver.NoAnswer:
        out = f"{domain}: no MX records — domain cannot receive email; set contact to null."
    except Exception as e:
        return f"Could not verify {domain} (DNS lookup failed: {e}). Treat as unverified."

    cache.set(key, out, ttl_seconds=_TTL)
    return out
