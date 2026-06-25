"""Seed Langfuse with accurate per-token prices for the OpenRouter models this app uses.

Langfuse computes cost as (token usage × model price), but its built-in price table only
knows mainstream slugs (gpt-*, claude-*, …) — not OpenRouter slugs like
`moonshotai/kimi-k2.7-code`. This script pulls live pricing from OpenRouter's own
`/models` API and registers a matching custom model in Langfuse for each slug the app can
use (primary + fallbacks + any per-agent overrides).

Run once after configuring Langfuse, and again whenever you change OPENROUTER_MODEL:

    python -m scripts.seed_langfuse_models        # from backend/, or
    python backend/scripts/seed_langfuse_models.py

Idempotent: a model with the same matchPattern is replaced.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

# Allow running as a bare script (python backend/scripts/seed_langfuse_models.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def _wanted_slugs(s) -> list[str]:
    """Every model slug this deployment might call: primary + fallbacks + agent overrides."""
    slugs = {s.openrouter_model, *s.fallback_models}
    try:
        from app.registries.agent_registry import AGENT_REGISTRY
        from app.registries.loader import load_builtins

        load_builtins()
        for a in AGENT_REGISTRY.list():
            if a.model:
                slugs.add(a.model)
    except Exception:
        pass
    return sorted(x for x in slugs if x)


def _openrouter_prices() -> dict[str, tuple[float, float]]:
    """slug -> (input_price_per_token, output_price_per_token) from OpenRouter."""
    resp = httpx.get(OPENROUTER_MODELS_URL, timeout=30)
    resp.raise_for_status()
    out: dict[str, tuple[float, float]] = {}
    for m in resp.json().get("data", []):
        pricing = m.get("pricing") or {}
        try:
            out[m["id"]] = (float(pricing.get("prompt", 0)), float(pricing.get("completion", 0)))
        except (TypeError, ValueError):
            continue
    return out


def _auth_header(s) -> dict[str, str]:
    token = base64.b64encode(
        f"{s.langfuse_public_key}:{s.langfuse_secret_key}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


def main() -> int:
    s = get_settings()
    if not s.langfuse_public_key or not s.langfuse_secret_key:
        print("Langfuse not configured (LANGFUSE_*_KEY missing) — nothing to seed.")
        return 1

    slugs = _wanted_slugs(s)
    print(f"Models to price: {slugs}")
    prices = _openrouter_prices()

    headers = {**_auth_header(s), "Content-Type": "application/json"}
    created, skipped = 0, 0
    for slug in slugs:
        if slug not in prices:
            print(f"  ! {slug}: not found in OpenRouter pricing — skipped")
            skipped += 1
            continue
        in_price, out_price = prices[slug]
        body = {
            "modelName": slug,
            "matchPattern": f"(?i)^{slug}$",
            "unit": "TOKENS",
            "inputPrice": in_price,
            "outputPrice": out_price,
        }
        r = httpx.post(
            f"{s.langfuse_host}/api/public/models", headers=headers, json=body, timeout=15
        )
        if r.status_code in (200, 201):
            print(f"  ✓ {slug}: in={in_price}/tok out={out_price}/tok")
            created += 1
        else:
            print(f"  ! {slug}: HTTP {r.status_code} {r.text[:200]}")
            skipped += 1

    print(f"\nDone — {created} priced, {skipped} skipped.")
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
