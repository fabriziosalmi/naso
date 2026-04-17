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
YELLOW="\033[1;33m"
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

check_docker_status() {
    print_step "SYSTEM" "Verifying Docker infrastructure"
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running or not accessible."
        exit 1
    fi
    
    if ! docker ps | grep -q "naso-api"; then
        print_error "The 'naso-api' container is not running. Please run 'make up' first."
        exit 1
    fi
    print_success "Infrastructure is online and healthy."
}

run_backend_tests() {
    print_step "BACKEND" "Executing PyTest Draconian Suite (API & AI Core)"
    # Discard warnings to keep the output beautiful, run in verbose mode for clarity
    if docker exec naso-api pytest tests/ -v -W ignore::DeprecationWarning; then
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
run_backend_tests
run_frontend_unit_tests
run_e2e_tests
print_summary
