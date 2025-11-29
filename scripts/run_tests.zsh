#!/usr/bin/env zsh

# TrainsAI - Test Runner Script
# Runs all unit tests and displays a clear summary

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory and project root
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"

echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
echo "${BOLD}${CYAN}           TrainsAI Unit Test Runner${NC}"
echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}\n"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [[ -d ".venv" ]]; then
    echo "${BLUE}→${NC} Activating virtual environment..."
    source .venv/bin/activate
else
    echo "${YELLOW}⚠${NC}  No virtual environment found (.venv)"
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "${RED}✗${NC} pytest not found. Installing..."
    pip install pytest pytest-cov pytest-mock
fi

echo "${BLUE}→${NC} Running all unit tests...\n"
echo "${CYAN}────────────────────────────────────────────────────────────${NC}\n"

# Run tests with verbose output and capture results
pytest test/ -v --tb=short --color=yes 2>&1 | tee /tmp/trainsai_test_output.txt

# Get exit code from pytest
TEST_EXIT_CODE=${PIPESTATUS[1]}

echo "\n${CYAN}────────────────────────────────────────────────────────────${NC}\n"

# Parse test results
TOTAL_TESTS=$(grep -E "collected [0-9]+ item" /tmp/trainsai_test_output.txt | grep -oE "[0-9]+" | head -1 || echo "0")
PASSED=$(grep -E "[0-9]+ passed" /tmp/trainsai_test_output.txt | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
FAILED=$(grep -E "[0-9]+ failed" /tmp/trainsai_test_output.txt | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
SKIPPED=$(grep -E "[0-9]+ skipped" /tmp/trainsai_test_output.txt | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")

# Display summary
echo "${BOLD}${CYAN}═══════════════════ TEST SUMMARY ═══════════════════${NC}\n"
echo "${BOLD}Total Tests:${NC}    $TOTAL_TESTS"
echo "${GREEN}${BOLD}✓ Passed:${NC}       $PASSED"

if [[ $FAILED -gt 0 ]]; then
    echo "${RED}${BOLD}✗ Failed:${NC}       $FAILED"
fi

if [[ $SKIPPED -gt 0 ]]; then
    echo "${YELLOW}${BOLD}⊘ Skipped:${NC}      $SKIPPED"
fi

# Calculate pass rate
if [[ $TOTAL_TESTS -gt 0 ]]; then
    PASS_RATE=$(echo "scale=1; ($PASSED * 100) / $TOTAL_TESTS" | bc)
    echo "\n${BOLD}Pass Rate:${NC}      ${PASS_RATE}%"
fi

# Display test modules
echo "\n${BOLD}Test Modules:${NC}"
echo "  • test_app.py                    (Flask application tests)"
echo "  • test_scotrail_agent.py         (ScotRail agent tests)"
echo "  • test_train_agent.py            (Train agent tests)"
echo "  • test_train_tools_comprehensive.py (Train tools tests)"

# Show failed tests if any
if [[ $FAILED -gt 0 ]]; then
    echo "\n${RED}${BOLD}Failed Tests:${NC}"
    grep "FAILED test/" /tmp/trainsai_test_output.txt | sed 's/FAILED /  • /' || echo "  (Details in output above)"
fi

echo "\n${CYAN}════════════════════════════════════════════════════════════${NC}\n"

# Final status
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo "${GREEN}${BOLD}✓ All tests passed!${NC}\n"
    exit 0
else
    echo "${YELLOW}${BOLD}⚠ Some tests failed or had issues${NC}\n"
    exit $TEST_EXIT_CODE
fi
