#!/usr/bin/env python3
"""Verify persona alignment between auth-api and unified-trading-api.

Checks that org IDs and persona names match across both services.
Exit 1 on mismatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directories to path for imports
workspace = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(workspace / "unified-trading-api"))
sys.path.insert(0, str(workspace / "auth-api"))


def main() -> int:
    errors: list[str] = []

    # Load unified-trading-api personas
    from unified_trading_api.mock_data.personas import ORGANIZATIONS, PERSONAS

    api_org_ids = {str(o["id"]) for o in ORGANIZATIONS}
    api_persona_ids = {str(p["id"]) for p in PERSONAS}
    api_persona_orgs = {str(p["id"]): str(p["org_id"]) for p in PERSONAS}

    # Load auth-api mock data
    try:
        from auth_api.mock_state import get_store

        store = get_store()
        auth_org_ids = set(store.orgs.keys())
        auth_user_ids = set(store.users.keys())
        auth_user_orgs = {uid: u.org_id for uid, u in store.users.items()}
    except ImportError:
        print("WARNING: auth-api not importable — skipping auth-api checks")
        return 0

    # Check org alignment
    api_only_orgs = api_org_ids - auth_org_ids
    auth_only_orgs = auth_org_ids - api_org_ids
    if api_only_orgs:
        errors.append(f"Orgs in unified-trading-api but NOT auth-api: {api_only_orgs}")
    if auth_only_orgs:
        errors.append(f"Orgs in auth-api but NOT unified-trading-api: {auth_only_orgs}")

    # Check persona alignment
    api_only_personas = api_persona_ids - auth_user_ids
    auth_only_personas = auth_user_ids - api_persona_ids
    if api_only_personas:
        errors.append(f"Personas in unified-trading-api but NOT auth-api: {api_only_personas}")
    if auth_only_personas:
        errors.append(f"Personas in auth-api but NOT unified-trading-api: {auth_only_personas}")

    # Check org_id mapping
    for pid in api_persona_ids & auth_user_ids:
        api_org = api_persona_orgs.get(pid, "")
        auth_org = auth_user_orgs.get(pid, "")
        if api_org != auth_org:
            errors.append(
                f"Persona '{pid}' org mismatch: api={api_org}, auth={auth_org}"
            )

    if errors:
        print("PERSONA ALIGNMENT FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"PERSONA ALIGNMENT OK: {len(api_org_ids)} orgs, {len(api_persona_ids)} personas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
