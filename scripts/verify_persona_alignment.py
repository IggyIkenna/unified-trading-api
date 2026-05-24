#!/usr/bin/env python3
"""Verify persona alignment between auth-api and unified-trading-api.

Checks that org IDs, persona names, emails, roles, and entitlements match
across both services. Also validates internal consistency of the trading-api
persona data (e.g. all persona org_ids reference valid orgs).

Exit 0 if aligned, exit 1 with diff on mismatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directories to path for imports
_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent
_workspace = _repo_root.parent
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_workspace / "auth-api"))


def _validate_internal_consistency(
    organizations: list[dict[str, object]],
    personas: list[dict[str, object]],
    entitlements: dict[str, dict[str, object]],
) -> list[str]:
    """Validate internal consistency of trading-api persona data."""
    errors: list[str] = []

    org_ids = {str(o["id"]) for o in organizations}

    # Every persona must reference a valid org
    for p in personas:
        pid = str(p["id"])
        org_id = str(p["org_id"])
        if org_id not in org_ids:
            errors.append(f"Persona '{pid}' references unknown org_id '{org_id}'")

    # Every persona entitlement must be a known entitlement (or wildcard)
    known_entitlements = set(entitlements.keys()) | {"*"}
    for p in personas:
        pid = str(p["id"])
        p_entitlements = p.get("entitlements", [])
        if not isinstance(p_entitlements, list):
            errors.append(f"Persona '{pid}' has non-list entitlements: {p_entitlements}")
            continue
        for ent in p_entitlements:
            if str(ent) not in known_entitlements:
                errors.append(f"Persona '{pid}' has unknown entitlement '{ent}'")

    # Org IDs must be unique
    org_id_list = [str(o["id"]) for o in organizations]
    if len(org_id_list) != len(set(org_id_list)):
        errors.append(f"Duplicate org IDs found: {org_id_list}")

    # Persona IDs must be unique
    persona_id_list = [str(p["id"]) for p in personas]
    if len(persona_id_list) != len(set(persona_id_list)):
        errors.append(f"Duplicate persona IDs found: {persona_id_list}")

    return errors


def _check_org_alignment(
    api_org_ids: set[str],
    auth_org_ids: set[str],
    api_org_names: dict[str, str],
    auth_org_names: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    api_only = api_org_ids - auth_org_ids
    auth_only = auth_org_ids - api_org_ids
    if api_only:
        errors.append(f"Orgs in unified-trading-api but NOT auth-api: {sorted(api_only)}")
    if auth_only:
        errors.append(f"Orgs in auth-api but NOT unified-trading-api: {sorted(auth_only)}")
    for oid in api_org_ids & auth_org_ids:
        api_name = api_org_names.get(oid, "")
        auth_name = auth_org_names.get(oid, "")
        if api_name != auth_name:
            errors.append(f"Org '{oid}' name mismatch: api='{api_name}', auth='{auth_name}'")
    return errors


def _check_persona_fields(
    pid: str,
    api_persona_orgs: dict[str, str],
    auth_user_orgs: dict[str, str],
    api_persona_emails: dict[str, str],
    auth_user_emails: dict[str, str],
    api_persona_names: dict[str, str],
    auth_user_names: dict[str, str],
    api_persona_roles: dict[str, str],
    auth_user_roles: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    api_org, auth_org = api_persona_orgs.get(pid, ""), auth_user_orgs.get(pid, "")
    if api_org != auth_org:
        errors.append(f"Persona '{pid}' org_id mismatch: api='{api_org}', auth='{auth_org}'")
    api_email, auth_email = api_persona_emails.get(pid, ""), auth_user_emails.get(pid, "")
    if api_email != auth_email:
        errors.append(f"Persona '{pid}' email mismatch: api='{api_email}', auth='{auth_email}'")
    api_dname, auth_name = api_persona_names.get(pid, ""), auth_user_names.get(pid, "")
    if api_dname != auth_name:
        errors.append(f"Persona '{pid}' name mismatch: api='{api_dname}', auth='{auth_name}'")
    api_role, auth_role = api_persona_roles.get(pid, ""), auth_user_roles.get(pid, "")
    if api_role != auth_role:
        errors.append(f"Persona '{pid}' role mismatch: api='{api_role}', auth='{auth_role}'")
    return errors


def _check_persona_alignment(
    api_persona_ids: set[str],
    auth_user_ids: set[str],
    api_persona_orgs: dict[str, str],
    auth_user_orgs: dict[str, str],
    api_persona_emails: dict[str, str],
    auth_user_emails: dict[str, str],
    api_persona_names: dict[str, str],
    auth_user_names: dict[str, str],
    api_persona_roles: dict[str, str],
    auth_user_roles: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    api_only = api_persona_ids - auth_user_ids
    auth_only = auth_user_ids - api_persona_ids
    if api_only:
        errors.append(f"Personas in unified-trading-api but NOT auth-api: {sorted(api_only)}")
    if auth_only:
        errors.append(f"Personas in auth-api but NOT unified-trading-api: {sorted(auth_only)}")
    for pid in sorted(api_persona_ids & auth_user_ids):
        errors.extend(_check_persona_fields(
            pid, api_persona_orgs, auth_user_orgs,
            api_persona_emails, auth_user_emails,
            api_persona_names, auth_user_names,
            api_persona_roles, auth_user_roles,
        ))
    return errors


def _collect_org_persona_entitlements(oid: str, personas: list[dict[str, object]]) -> set[str]:
    result: set[str] = set()
    for p in personas:
        if str(p["org_id"]) == oid:
            p_ents = p.get("entitlements", [])
            if isinstance(p_ents, list):
                result.update(str(e) for e in p_ents)
    return result


def _check_entitlement_alignment(
    api_org_ids: set[str],
    auth_org_ids: set[str],
    personas: list[dict[str, object]],
    auth_org_entitlements: dict[str, set[str]],
) -> list[str]:
    errors: list[str] = []
    for oid in sorted(api_org_ids & auth_org_ids):
        auth_ents = auth_org_entitlements.get(oid, set())
        api_org_persona_ents = _collect_org_persona_entitlements(oid, personas)
        if "*" in api_org_persona_ents and "*" in auth_ents:
            continue
        if "*" in api_org_persona_ents or "*" in auth_ents:
            continue
        if auth_ents != api_org_persona_ents:
            missing_in_auth = api_org_persona_ents - auth_ents
            if missing_in_auth:
                errors.append(
                    f"Org '{oid}' entitlements: personas need {sorted(missing_in_auth)} "
                    f"but auth-api org only grants {sorted(auth_ents)}"
                )
    return errors


def _validate_cross_api_alignment(
    organizations: list[dict[str, object]],
    personas: list[dict[str, object]],
    entitlements: dict[str, dict[str, object]],
) -> list[str]:
    """Compare persona data between unified-trading-api and auth-api."""
    from auth_api.mock_data import MOCK_ORGS, MOCK_USERS

    api_org_ids = {str(o["id"]) for o in organizations}
    api_org_names = {str(o["id"]): str(o["name"]) for o in organizations}
    api_persona_ids = {str(p["id"]) for p in personas}
    api_persona_orgs = {str(p["id"]): str(p["org_id"]) for p in personas}
    api_persona_emails = {str(p["id"]): str(p["email"]) for p in personas}
    api_persona_names = {str(p["id"]): str(p["display_name"]) for p in personas}
    api_persona_roles = {str(p["id"]): str(p["role"]) for p in personas}

    auth_org_ids = {org.id for org in MOCK_ORGS}
    auth_org_names = {org.id: org.name for org in MOCK_ORGS}
    auth_org_entitlements = {org.id: set(org.entitlements) for org in MOCK_ORGS}
    auth_user_ids = {u.id for u in MOCK_USERS}
    auth_user_orgs = {u.id: u.org_id for u in MOCK_USERS}
    auth_user_emails = {u.id: u.email for u in MOCK_USERS}
    auth_user_names = {u.id: u.name for u in MOCK_USERS}
    auth_user_roles = {u.id: u.role.value for u in MOCK_USERS}

    errors: list[str] = []
    errors.extend(_check_org_alignment(api_org_ids, auth_org_ids, api_org_names, auth_org_names))
    errors.extend(_check_persona_alignment(
        api_persona_ids, auth_user_ids,
        api_persona_orgs, auth_user_orgs,
        api_persona_emails, auth_user_emails,
        api_persona_names, auth_user_names,
        api_persona_roles, auth_user_roles,
    ))
    errors.extend(_check_entitlement_alignment(api_org_ids, auth_org_ids, personas, auth_org_entitlements))
    return errors


def main() -> int:
    """Run persona alignment verification."""
    # Import trading-api persona data
    from unified_trading_api.mock_data.personas import (
        ENTITLEMENTS,
        ORGANIZATIONS,
        PERSONAS,
    )

    all_errors: list[str] = []

    # Phase 1: Internal consistency
    print("Checking internal consistency...")
    consistency_errors = _validate_internal_consistency(ORGANIZATIONS, PERSONAS, ENTITLEMENTS)
    all_errors.extend(consistency_errors)
    if consistency_errors:
        print(f"  {len(consistency_errors)} internal consistency issue(s)")
    else:
        print("  Internal consistency OK")

    # Phase 2: Cross-API alignment (if auth-api is available)
    auth_api_path = _workspace / "auth-api"
    if auth_api_path.is_dir():
        print("Checking cross-API alignment with auth-api...")
        try:
            cross_errors = _validate_cross_api_alignment(ORGANIZATIONS, PERSONAS, ENTITLEMENTS)
            all_errors.extend(cross_errors)
            if cross_errors:
                print(f"  {len(cross_errors)} cross-API alignment issue(s)")
            else:
                print("  Cross-API alignment OK")
        except ImportError as exc:
            print(f"  WARNING: auth-api not importable ({exc}) -- skipping cross-API checks")
    else:
        print("WARNING: auth-api not found at ../auth-api/ -- skipping cross-API checks")

    # Report
    if all_errors:
        print("\nPERSONA ALIGNMENT FAILED:")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    org_count = len(ORGANIZATIONS)
    persona_count = len(PERSONAS)
    entitlement_count = len(ENTITLEMENTS)
    print(f"\nPERSONA ALIGNMENT OK: {org_count} orgs, {persona_count} personas, {entitlement_count} entitlement types")
    return 0


if __name__ == "__main__":
    sys.exit(main())
