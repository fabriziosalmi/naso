#!/usr/bin/env bash

# ==============================================================================
# NASO FORENSIC ENGINE - DRACONIAN VALIDATION SCRIPT
# ==============================================================================
# This script executes the entire Draconian testing suite across Backend,
# Frontend, and end-to-end user flows. It is intended to be run before every
# commit to guarantee zero regressions.
# ==============================================================================

set -o pipefail

# ANSI Colors
CYAN="\033[1;36m"
GREEN="\033[1;32m"
RED="\033[1;31m"
MAGENTA="\033[1;35m"
RESET="\033[0m"
BOLD="\033[1m"

# Tally Counters
TESTS_PASSED=0
TESTS_FAILED=0

print_banner() {
    echo -e "\n${MAGENTA}======================================================${RESET}"
    echo -e "${MAGENTA} 🦅 NASO DRACONIAN VALIDATION SEQUENCE INITIATED 🦅 ${RESET}"
    echo -e "${MAGENTA}======================================================${RESET}\n"
}

print_step() {
    echo -e "${CYAN}▶ [$1]${RESET} $2..."
}

print_success() {
    echo -e "  ${GREEN}✔ SUCCESS${RESET}: $1\n"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "  ${RED}✖ FAILED${RESET}: $1\n"
    ((TESTS_FAILED++))
}

# How long to wait for naso-api to be running before giving up, in seconds.
API_WAIT_SECONDS="${NASO_API_WAIT_SECONDS:-60}"

# Everything we know about why naso-api is not running. Printed on failure so
# the run explains itself instead of leaving the next person to reproduce it.
#
# The single line this replaces -- `docker ps | grep -q naso-api` -- produced
# three red CI builds in which the API had answered a request seconds earlier.
# One-shot and silent, it could not distinguish "never started" from "restarted
# once between the health gate and here", and it printed nothing either way, so
# each failure cost a full re-run to learn anything at all.
dump_api_diagnostics() {
    echo -e "${RED}--- docker compose ps -a ---${RESET}"
    docker compose ps -a 2>&1 || true
    echo -e "${RED}--- naso-api state ---${RESET}"
    docker inspect -f \
        'status={{.State.Status}} exit={{.State.ExitCode}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} error={{.State.Error}}' \
        naso-api 2>&1 || echo "no container named naso-api exists"
    echo -e "${RED}--- last 80 lines of backend log ---${RESET}"
    docker compose logs --no-color --tail=80 backend 2>&1 || true
}

check_docker_status() {
    print_step "SYSTEM" "Verifying Docker infrastructure"
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running or not accessible."
        exit 1
    fi

    # Poll rather than sample once. A container that is mid-restart is reported
    # as not running for a second or two, which is a real state worth waiting
    # out -- but only briefly: a crash loop never converges, and the diagnostics
    # below are what tell the two apart.
    local waited=0
    local state=""
    while [ "$waited" -lt "$API_WAIT_SECONDS" ]; do
        state="$(docker inspect -f '{{.State.Status}}' naso-api 2>/dev/null || echo absent)"
        [ "$state" = "running" ] && break
        sleep 2
        waited=$((waited + 2))
    done

    if [ "$state" != "running" ]; then
        print_error "The 'naso-api' container is '${state}' after ${API_WAIT_SECONDS}s (expected 'running'). Try 'make up' first."
        dump_api_diagnostics
        exit 1
    fi

    if [ "$waited" -gt 0 ]; then
        echo -e "  ${CYAN}note${RESET}: naso-api took ${waited}s to report 'running'."
    fi
    print_success "Infrastructure is online and healthy."
}

# How long to wait for every container to settle, and for the composite health
# endpoint to report all-clear.
STACK_WAIT_SECONDS="${NASO_STACK_WAIT_SECONDS:-180}"

# The gate above checks one container. That was the whole of it, and it is why
# this script printed "ALL SYSTEMS NOMINAL" while six containers were in a
# permanent crash loop: the five Tor instances could not create their data
# directory and the haproxy front end aborted at boot because their names did
# not resolve. Every CI run was green throughout.
#
# A container that is `restarting` is not a slow start, it is a failure with a
# retry attached, so it has to fail the build.
check_stack_state() {
    print_step "SYSTEM" "Verifying every container reaches a steady running state"

    local waited=0
    local report=""
    while [ "$waited" -lt "$STACK_WAIT_SECONDS" ]; do
        report="$(docker compose ps -a --format json 2>/dev/null | python3 -c '
import json, sys

bad = []
seen = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    # Compose v2 emits one JSON object per line; some versions emit one array.
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        continue
    for c in parsed if isinstance(parsed, list) else [parsed]:
        seen += 1
        name = c.get("Name", "?")
        state = (c.get("State") or "").lower()
        health = (c.get("Health") or "").lower()
        # No backslashes inside f-string expressions: that is a syntax error
        # before Python 3.12, and this runs on whatever the host provides.
        if state != "running":
            bad.append(name + ": " + (state or "unknown"))
        elif health == "unhealthy":
            bad.append(name + ": running but unhealthy")
        elif health == "starting":
            bad.append(name + ": health starting")
if not seen:
    print("NONE no containers found")
elif bad:
    print("BAD " + "; ".join(bad))
else:
    print("OK " + str(seen))
')"
        case "$report" in
            OK*) break ;;
        esac
        sleep 3
        waited=$((waited + 3))
    done

    case "$report" in
        OK*)
            echo -e "  ${CYAN}note${RESET}: ${report#OK } containers running (settled in ${waited}s)."
            print_success "Every container is running."
            ;;
        *)
            print_error "Containers did not settle within ${STACK_WAIT_SECONDS}s — ${report#* }"
            docker compose ps -a 2>&1 || true
            exit 1
            ;;
    esac
}

# `/system/status` answers 200 with {"status": "degraded"} when a dependency is
# down, and the composite endpoint answers 503 with the component that broke.
# Neither was ever checked here, so an Elasticsearch the application could not
# reach — it spoke https to a plaintext listener for months — never failed a
# build either.
#
# `disabled` is a pass: Elasticsearch and MinIO are optional, and a minimal
# install that leaves them unconfigured is a correct install.
check_composite_health() {
    print_step "SYSTEM" "Verifying /system/health reports every component healthy"

    local waited=0
    local report=""
    while [ "$waited" -lt "$STACK_WAIT_SECONDS" ]; do
        report="$(curl -s --max-time 15 http://localhost:8000/system/health 2>/dev/null | python3 -c '
import json, sys

try:
    d = json.load(sys.stdin)
except Exception:
    print("BAD endpoint returned no parsable JSON")
    raise SystemExit(0)
components = d.get("components") or {}
if not components:
    print("BAD response carried no components")
    raise SystemExit(0)
def describe(item):
    return item[0] + "=" + str(item[1].get("status"))

bad = [describe(i) for i in components.items() if i[1].get("status") not in ("ok", "disabled")]
if bad:
    print("BAD " + ", ".join(bad))
else:
    print("OK " + ", ".join(describe(i) for i in sorted(components.items())))
')"
        case "$report" in
            OK*) break ;;
        esac
        sleep 3
        waited=$((waited + 3))
    done

    case "$report" in
        OK*)
            echo -e "  ${CYAN}note${RESET}: ${report#OK }"
            print_success "Composite health is clear."
            ;;
        *)
            print_error "Composite health never cleared within ${STACK_WAIT_SECONDS}s — ${report#* }"
            curl -s --max-time 15 http://localhost:8000/system/health 2>&1 | head -40
            exit 1
            ;;
    esac
}

run_backend_tests() {
    print_step "BACKEND" "Executing PyTest Draconian Suite (API & AI Core)"
    # -p no:cacheprovider: the API container has a read_only root filesystem, so
    # pytest cannot write .pytest_cache and emits two warnings per run about it.
    if docker exec naso-api pytest tests/ -v -W ignore::DeprecationWarning -p no:cacheprovider; then
        print_success "Backend Core tests passed."
    else
        print_error "Backend Core tests failed."
    fi
}

run_frontend_unit_tests() {
    print_step "FRONTEND" "Executing Vitest Component & Store Suite"
    cd frontend || exit 1

    # Run vitest in run mode (single execution, no watch)
    if npm run test -- --run --reporter=verbose; then
        print_success "Frontend React layer passed."
    else
        print_error "Frontend React layer failed."
    fi
    cd ..
}

run_e2e_tests() {
    print_step "PLAYWRIGHT" "Executing End-to-End Analyst UI Flows"
    cd frontend || exit 1

    # Ensure Playwright browsers are installed silently, then run the UI test
    npx playwright install chromium >/dev/null 2>&1

    if npx playwright test; then
        print_success "E2E User flows passed smoothly."
    else
        print_error "E2E User flows encountered failures."
    fi
    cd ..
}

print_summary() {
    echo -e "${MAGENTA}======================================================${RESET}"
    echo -e "${BOLD}DRACONIAN VALIDATION SUMMARY${RESET}"
    echo -e "${MAGENTA}======================================================${RESET}"

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}ALL SYSTEMS NOMINAL. YOU ARE CLEARED TO PUSH.${RESET} 🚀"
        echo -e "Modules passed: ${TESTS_PASSED}"
        exit 0
    else
        echo -e "${RED}SYSTEM COMPROMISED. REGRESSIONS DETECTED.${RESET} ⚠️"
        echo -e "Modules failed: ${TESTS_FAILED}"
        echo -e "Do NOT commit until all tests are green."
        exit 1
    fi
}

# --- MAIN EXECUTION ---
print_banner
check_docker_status
check_stack_state
check_composite_health
run_backend_tests
run_frontend_unit_tests
run_e2e_tests
print_summary
