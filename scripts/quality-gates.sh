#!/usr/bin/env bash
# Repo-specific settings only. Body: unified-trading-pm/scripts/quality-gates-base/base-service.sh
# SSOT: unified-trading-codex/06-coding-standards/quality-gates-service-template.sh
#
# Instructions for a new service:
#   1. Copy this to scripts/quality-gates.sh in your repo (rollout-quality-gates-unified.py does this)
#   2. SERVICE_NAME, SOURCE_DIR, and MIN_COVERAGE are set automatically by rollout (floor=70)
#   3. Set RUN_INTEGRATION=true only if your repo has integration tests
#   4. Add LOCAL_DEPS entries if your service has local editable deps (e.g. unified-events-interface)
SERVICE_NAME="unified-trading-api"
SOURCE_DIR="unified_trading_api"
MIN_COVERAGE=70
RUN_INTEGRATION=true
PYTEST_WORKERS=${PYTEST_WORKERS:-}  # default: max(1, cpu_count//4) computed by base script
LOCAL_DEPS=()
# seed.py (5043L) and seed_all_domains() (4834L) are generated mock data — exempt from size checks
FUNCTION_SIZE_EXTRA_EXCLUDES=("! -path ./unified_trading_api/mock_data/seed.py" "! -path ./unified_trading_api/mock_data/seed_strategies.py")
# seed.py has many .get("key", "") patterns for mock data dict access — intentional
EMPTY_STR_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py" "!**/chat.py")
EMPTY_DICT_LIST_EXCLUDE_GLOBS=("!**/mock_data/seed.py" "!**/mock_data/seed_*.py")
# main.py has conditional imports inside lifespan()/create_app() (mock vs real mode);
# seed.py/seed_phase8.py defer heavy imports to reduce startup time;
# auth.py defers jwt import to avoid import cycle
IMPORT_INSIDE_EXCLUDE_GLOBS=("!**/main.py" "!**/seed.py" "!**/seed_phase8.py" "!**/auth.py" "!**/chat.py")
WORKSPACE_ROOT="$(cd "$(git rev-parse --show-toplevel)/.." && pwd)"
source "${WORKSPACE_ROOT}/unified-trading-pm/scripts/quality-gates-base/base-service.sh"

# Codex enforcement: every entrypoint must emit STARTED, STOPPED, FAILED
# See: unified-trading-codex/03-observability/lifecycle-events.md § Lifecycle Event QG Enforcement
log_section "[5.X/6] UEI LIFECYCLE EVENT ENFORCEMENT (STARTED/STOPPED/FAILED)"
for event in STARTED STOPPED FAILED; do
    run_timeout 30 rg "log_event.*\"${event}\"" "${SOURCE_DIR}" --type py -q \
        || log_warn "Missing log_event('${event}') in ${SERVICE_NAME} — see codex 03-observability/lifecycle-events.md"
done
