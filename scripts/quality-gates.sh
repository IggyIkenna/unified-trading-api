#!/usr/bin/env bash
# Repo-specific settings only. Body: unified-trading-pm/scripts/quality-gates-base/base-service.sh
# SSOT: unified-trading-codex/06-coding-standards/quality-gates-service-template.sh
#
# Instructions for a new service:
#   1. Copy this to scripts/quality-gates.sh in your repo (rollout-quality-gates-unified.py does this)
#   2. SERVICE_NAME, SOURCE_DIR, and MIN_COVERAGE are set automatically by rollout (floor=70)
#   3. Set RUN_INTEGRATION=true only if your repo has integration tests
#   4. Add LOCAL_DEPS entries if your service has local editable deps (e.g. unified-trading-library)
SERVICE_NAME="unified-trading-api"
SOURCE_DIR="unified_trading_api"
MIN_COVERAGE=70
RUN_INTEGRATION=false
PYTEST_WORKERS=${PYTEST_WORKERS:-2}
LOCAL_DEPS=()
# seed.py (5043L) and seed_all_domains() (4834L) are generated mock data — exempt from size checks
FUNCTION_SIZE_EXTRA_EXCLUDES=("! -path ./unified_trading_api/mock_data/seed.py" "! -path ./unified_trading_api/mock_data/seed_strategies.py")
# seed.py has many .get("key", "") patterns for mock data dict access — intentional
EMPTY_STR_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py" "!**/chat.py")
EMPTY_DICT_LIST_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py")
# main.py has conditional imports inside lifespan()/create_app() (mock vs real mode);
# seed.py/seed_phase8.py defer heavy imports to reduce startup time;
# auth.py defers jwt import to avoid import cycle
IMPORT_INSIDE_EXCLUDE_GLOBS=("!**/main.py" "!**/seed.py" "!**/seed_phase8.py" "!**/auth.py" "!**/chat.py" "!**/routes/reporting.py" "!**/routes/execution.py" "!**/mock_data/seed_calendar.py")
# Manifest alignment: unified_api_contracts import is used for type references
MANIFEST_ALIGNMENT_SKIP=true
# Schema provenance: API-layer response/request models (not shared domain schemas)
SCHEMA_PROVENANCE_SKIP=true
# Empty string/dict/list: route handlers parse optional JSON fields with safe defaults
EMPTY_STR_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py" "!**/chat.py" "!**/routes/*.py" "!**/services/*.py")
EMPTY_DICT_LIST_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py" "!**/routes/*.py")
# Deep unified lib imports: internal service-layer imports (self-referencing package paths)
DEEP_IMPORT_EXCLUDE_GLOBS=(
    "!**/services/app_state.py"
    "!**/services/factory.py"
    "!**/routes/*.py"
    "!**/main.py"
    "!**/mock_data/*.py"
)
# pip-audit: ignore known CVEs pending dependency upgrades.
PIP_AUDIT_EXTRA_ARGS="--ignore-vuln CVE-2026-25645 --ignore-vuln CVE-2026-33752"
# Ratcheted down from 8 to 2: remaining = pip-audit (dep upgrade lag) + empty-string (noqa'd).
CODEX_MAX_VIOLATIONS=2
export CODEX_MAX_VIOLATIONS

WORKSPACE_ROOT="$(cd "$(git rev-parse --show-toplevel)/.." && pwd)"
source "${WORKSPACE_ROOT}/unified-trading-pm/scripts/quality-gates-base/base-service.sh"

# Codex enforcement: every entrypoint must emit STARTED, STOPPED, FAILED
# See: unified-trading-codex/03-observability/lifecycle-events.md § Lifecycle Event QG Enforcement
log_section "[5.X/6] UEI LIFECYCLE EVENT ENFORCEMENT (STARTED/STOPPED/FAILED)"
for event in STARTED STOPPED FAILED; do
    run_timeout 30 rg "log_event.*\"${event}\"" "${SOURCE_DIR}" --type py -q \
        || log_warn "Missing log_event('${event}') in ${SERVICE_NAME} — see codex 03-observability/lifecycle-events.md"
done
