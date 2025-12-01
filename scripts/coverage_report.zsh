#!/usr/bin/env zsh

# TrainsAI - Coverage Report Script
# Runs all unit tests with coverage analysis and generates detailed reports

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory and project root
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"

echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
echo "${BOLD}${CYAN}        TrainsAI Code Coverage Report Generator${NC}"
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

# Check if pytest-cov is available
if ! python -c "import pytest_cov" 2>/dev/null; then
    echo "${YELLOW}⚠${NC}  pytest-cov not found. Installing..."
    pip install pytest-cov
fi

echo "${BLUE}→${NC} Running tests with coverage analysis...\n"
echo "${CYAN}────────────────────────────────────────────────────────────${NC}\n"

# Run tests with coverage
pytest test/ \
    --cov=. \
    --cov-report=term \
    --cov-report=html \
    --cov-report=term-missing \
    -q \
    --tb=no

# Get exit code from pytest
TEST_EXIT_CODE=$?

echo "\n${CYAN}────────────────────────────────────────────────────────────${NC}\n"

# Parse coverage results from the output
if [[ -f ".coverage" ]]; then
    # Extract coverage percentage using coverage tool
    COVERAGE_PCT=$(python -c "
try:
    from coverage import Coverage
    cov = Coverage()
    cov.load()
    total = cov.report(show_missing=False)
    print(f'{total:.1f}')
except Exception as e:
    print('N/A')
" 2>/dev/null || echo "N/A")
    
    echo "${BOLD}${CYAN}═══════════════════ COVERAGE SUMMARY ═══════════════════${NC}\n"
    
    if [[ "$COVERAGE_PCT" != "N/A" ]]; then
        # Color code based on coverage percentage
        if (( $(echo "$COVERAGE_PCT >= 90" | bc -l 2>/dev/null || echo 0) )); then
            COVERAGE_COLOR="${GREEN}"
            STATUS_ICON="✓"
        elif (( $(echo "$COVERAGE_PCT >= 75" | bc -l 2>/dev/null || echo 0) )); then
            COVERAGE_COLOR="${YELLOW}"
            STATUS_ICON="⚠"
        else
            COVERAGE_COLOR="${RED}"
            STATUS_ICON="✗"
        fi
        
        echo "${COVERAGE_COLOR}${BOLD}${STATUS_ICON} Overall Coverage:${NC} ${COVERAGE_COLOR}${BOLD}${COVERAGE_PCT}%${NC}\n"
    fi
    
    echo "${BOLD}Coverage Reports Generated:${NC}"
    echo "  ${MAGENTA}•${NC} Terminal: Displayed above"
    echo "  ${MAGENTA}•${NC} HTML: htmlcov/index.html"
    echo "  ${MAGENTA}•${NC} Data: .coverage\n"
    
    echo "${BOLD}View HTML Report:${NC}"
    echo "  ${BLUE}open htmlcov/index.html${NC}\n"
    
    # Show file-by-file breakdown summary
    echo "${BOLD}Key Files Coverage:${NC}"
    python -c "
try:
    from coverage import Coverage
    import sys
    
    cov = Coverage()
    cov.load()
    
    # Get coverage data
    analysis = []
    for filename in cov.get_data().measured_files():
        if not filename.startswith('test/') and not filename.startswith('.venv/'):
            try:
                stats = cov.analysis2(filename)
                total_lines = len(stats[1]) + len(stats[2])
                covered_lines = len(stats[1])
                if total_lines > 0:
                    pct = (covered_lines / total_lines) * 100
                    # Only show main application files
                    if 'app.py' in filename or 'train' in filename or 'scotrail' in filename:
                        analysis.append((filename.split('/')[-1], pct, covered_lines, total_lines))
            except:
                pass
    
    # Sort by coverage percentage (ascending to show worst first)
    analysis.sort(key=lambda x: x[1])
    
    # Show results
    for name, pct, covered, total in analysis[:10]:  # Show top 10
        color = '\033[0;32m' if pct >= 90 else '\033[1;33m' if pct >= 75 else '\033[0;31m'
        reset = '\033[0m'
        print(f'  {color}▪{reset} {name:40s} {color}{pct:5.1f}%{reset}  ({covered}/{total} lines)')
except Exception as e:
    print(f'  Error generating file breakdown: {e}', file=sys.stderr)
"
    
    echo ""
    
    # Show uncovered lines for critical files
    echo "${BOLD}Uncovered Lines in Critical Files:${NC}"
    python -c "
try:
    from coverage import Coverage
    
    cov = Coverage()
    cov.load()
    
    critical_files = ['app.py', 'scotrail_agent.py', 'train_tools.py']
    
    for filename in cov.get_data().measured_files():
        fname = filename.split('/')[-1]
        if fname in critical_files:
            try:
                stats = cov.analysis2(filename)
                missing_lines = stats[2]
                if missing_lines:
                    # Group consecutive lines
                    ranges = []
                    start = missing_lines[0]
                    end = missing_lines[0]
                    
                    for line in missing_lines[1:]:
                        if line == end + 1:
                            end = line
                        else:
                            ranges.append(f'{start}-{end}' if start != end else str(start))
                            start = end = line
                    ranges.append(f'{start}-{end}' if start != end else str(start))
                    
                    print(f'  \033[1;33m▪\033[0m {fname:30s} Lines: {', '.join(ranges[:5])}{'...' if len(ranges) > 5 else ''}')
            except:
                pass
except Exception as e:
    pass
"
    
else
    echo "${RED}${BOLD}✗ No coverage data found${NC}"
fi

echo "\n${CYAN}════════════════════════════════════════════════════════════${NC}\n"

# Final status
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo "${GREEN}${BOLD}✓ Coverage report generated successfully!${NC}\n"
    exit 0
else
    echo "${YELLOW}${BOLD}⚠ Tests completed with issues${NC}\n"
    exit $TEST_EXIT_CODE
fi
