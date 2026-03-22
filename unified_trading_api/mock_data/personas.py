"""Persona SSOT — shared between auth-api and UI.

Defines organizations, personas, and entitlements for mock/demo mode.
Both auth-api and the UI's persona switcher use these same IDs.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

ORGANIZATIONS: Final[list[dict[str, object]]] = [
    {
        "id": "odum-internal",
        "name": "Odum Internal",
        "type": "internal",
        "aum": 18_000_000,
    },
    {
        "id": "acme",
        "name": "Alpha Capital",
        "type": "external",
        "aum": 15_000_000,
    },
    {
        "id": "beta",
        "name": "Beta Fund",
        "type": "external",
        "aum": 5_000_000,
    },
    {
        "id": "vertex",
        "name": "Vertex Partners",
        "type": "external",
        "aum": 15_000_000,
    },
]

ORG_IDS: Final[list[str]] = [str(o["id"]) for o in ORGANIZATIONS]

# ---------------------------------------------------------------------------
# Personas (demo login identities)
# ---------------------------------------------------------------------------

PERSONAS: Final[list[dict[str, object]]] = [
    {
        "id": "admin",
        "email": "admin@odum.internal",
        "display_name": "Admin",
        "org_id": "odum-internal",
        "role": "admin",
        "entitlements": ["*"],
        "description": "Full system admin — sees everything",
    },
    {
        "id": "internal-trader",
        "email": "trader@odum.internal",
        "display_name": "Internal Trader",
        "org_id": "odum-internal",
        "role": "internal",
        "entitlements": ["*"],
        "description": "Internal trading desk",
    },
    {
        "id": "client-full",
        "email": "pm@alphacapital.com",
        "display_name": "Portfolio Manager",
        "org_id": "acme",
        "role": "client",
        "entitlements": [
            "data-pro",
            "execution-full",
            "ml-full",
            "strategy-full",
            "reporting",
        ],
        "description": "External client with full subscription",
    },
    {
        "id": "client-data-only",
        "email": "analyst@betafund.com",
        "display_name": "Data Analyst",
        "org_id": "beta",
        "role": "client",
        "entitlements": ["data-basic"],
        "description": "Basic data tier (180 instruments, CeFi only)",
    },
    {
        "id": "client-premium",
        "email": "cio@vertex.com",
        "display_name": "CIO",
        "org_id": "vertex",
        "role": "client",
        "entitlements": ["data-pro", "execution-full", "strategy-full"],
        "description": "Premium execution client (no ML)",
    },
]

# ---------------------------------------------------------------------------
# Entitlement definitions
# ---------------------------------------------------------------------------

ENTITLEMENTS: Final[dict[str, dict[str, object]]] = {
    "data-basic": {
        "label": "Data Basic",
        "categories": ["cefi"],
        "max_instruments": 180,
    },
    "data-pro": {
        "label": "Data Pro",
        "categories": ["cefi", "defi", "tradfi", "sports", "prediction"],
        "max_instruments": None,
    },
    "execution-full": {"label": "Execution Full"},
    "ml-full": {"label": "ML Full"},
    "strategy-full": {"label": "Strategy Full"},
    "reporting": {"label": "Reporting"},
}
