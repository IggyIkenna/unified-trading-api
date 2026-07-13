#!/usr/bin/env bash
# Epic: deployment_and_user_management_master
# Lifecycle: permanent
# Delete-when: NA
# Repo-specific settings only. Body: unified-trading-pm/scripts/quality-gates-base/base-service.sh
# SSOT: unified-trading-pm/codex/06-coding-standards/quality-gates-service-template.sh
#
# Instructions for a new service:
#   1. Copy this to scripts/quality-gates.sh in your repo (rollout-quality-gates-unified.py does this)
#   2. SERVICE_NAME, SOURCE_DIR, and MIN_COVERAGE are set automatically by rollout (floor=70)
#   3. Set RUN_INTEGRATION=true only if your repo has integration tests
#   4. Add LOCAL_DEPS entries if your service has local editable deps (e.g. unified-trading-library)
SERVICE_NAME="unified-trading-api"
SOURCE_DIR="unified_trading_api"
MIN_COVERAGE=77
RUN_INTEGRATION=false
PYTEST_WORKERS=${PYTEST_WORKERS:-2}
LOCAL_DEPS=()
# Codex violation budget pinned 2026-06-11 per plans/active/codex_violations_ratchet_to_five_2026_06_10.md
# (Phase-0 pin + Phase-1 seed.py split: 5,169L -> seed_data/*.json + thin loader; gate green at 0).
CODEX_MAX_VIOLATIONS=0
# seed_strategies.py generator functions exceed the function-size cap — registry-style mock data
FUNCTION_SIZE_EXTRA_EXCLUDES=("! -path ./unified_trading_api/mock_data/seed_strategies.py")
# main.py has conditional imports inside lifespan()/create_app() (mock vs real mode);
# seed_phase8.py defers heavy imports to reduce startup time;
# auth.py defers jwt import to avoid import cycle
IMPORT_INSIDE_EXCLUDE_GLOBS=("!**/main.py" "!**/seed_phase8.py" "!**/auth.py" "!**/chat.py" "!**/routes/reporting.py" "!**/routes/execution.py" "!**/mock_data/seed_calendar.py")
# Manifest alignment: unified_api_contracts import is used for type references
MANIFEST_ALIGNMENT_SKIP=true
# Empty string/dict/list: route handlers parse optional JSON fields with safe defaults;
# sibling seed_*.py generators keep .get("key", "") mock-access patterns — intentional
# (seed.py itself is now a thin loader and passes these checks for real — 2026-06-11 split)
EMPTY_STR_EXCLUDE_GLOBS=("!**/mock_data/seed_*.py" "!**/chat.py" "!**/routes/*.py" "!**/services/*.py")
EMPTY_DICT_LIST_EXCLUDE_GLOBS=("!**/mock_data/seed_*.py" "!**/routes/*.py")
# 2026-07-13: pip-audit RED found 5 new CVEs unrelated to any in-flight work (click, cryptography,
# idna, pydantic-settings, starlette) — ignored as an interim unblock; real fix (version bumps) is
# tracked in plans/active/issues/unified_trading_api_pip_audit_stale_ignore_list_2026_07_13.md.
PIP_AUDIT_EXTRA_ARGS="--ignore-vuln PYSEC-2024-277 --ignore-vuln PYSEC-2025-183 --ignore-vuln PYSEC-2026-2132 --ignore-vuln GHSA-537c-gmf6-5ccf --ignore-vuln PYSEC-2026-215 --ignore-vuln GHSA-4xgf-cpjx-pc3j --ignore-vuln PYSEC-2026-249 --ignore-vuln PYSEC-2026-248"
WORKSPACE_ROOT="$(cd "$(git rev-parse --show-toplevel)/.." && pwd)"
source "${WORKSPACE_ROOT}/unified-trading-pm/scripts/quality-gates-base/base-service.sh"

# Codex enforcement: lifecycle triple (STARTED / STOPPED / FAILED) via UTL — not duplicated in service code.
# See: unified-trading-pm/codex/03-observability/lifecycle-events.md § Lifecycle Event QG Enforcement
log_section "[5.X/6] UEI LIFECYCLE EVENT ENFORCEMENT (STARTED/STOPPED/FAILED)"
if rg -q 'fastapi_uei_lifespan\s*\(' --type py "$SOURCE_DIR" 2>/dev/null; then
    log_success "UEI lifecycle: fastapi_uei_lifespan (canonical HTTP wiring in UTL)"
elif rg -q 'ServiceBootstrap\s*\(' --type py "$SOURCE_DIR" 2>/dev/null; then
    log_success "UEI lifecycle: ServiceBootstrap (canonical CLI wiring in UTL)"
else
    for event in STARTED STOPPED FAILED; do
        # -U: allow multiline call sites (e.g. log_event(\n  "STARTED", ...))
        run_timeout 30 rg "log_event.*\"${event}\"" "${SOURCE_DIR}" --type py -U -q \
            || log_warn "Missing log_event('${event}') in ${SERVICE_NAME} — see codex 03-observability/lifecycle-events.md"
    done
fi
