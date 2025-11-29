#!/usr/bin/env zsh

# TrainsAI - Development Server Script
# Runs the Flask application in debug mode with hot-reload

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
echo "${BOLD}${CYAN}        TrainsAI Development Server${NC}"
echo "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}\n"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [[ -d ".venv" ]]; then
    echo "${BLUE}→${NC} Activating virtual environment..."
    source .venv/bin/activate
else
    echo "${RED}✗${NC} No virtual environment found (.venv)"
    echo "${YELLOW}→${NC} Create one with: python -m venv .venv"
    exit 1
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo "${YELLOW}⚠${NC}  No .env file found"
    echo "${BLUE}→${NC} Copy .env.example to .env and configure your API keys"
    if [[ -f ".env.example" ]]; then
        echo "${BLUE}→${NC} Run: cp .env.example .env"
    fi
    echo ""
fi

# Check for required dependencies
echo "${BLUE}→${NC} Checking dependencies..."
if ! python -c "import flask" 2>/dev/null; then
    echo "${YELLOW}⚠${NC}  Flask not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Configuration from environment or defaults
export FLASK_DEBUG="${FLASK_DEBUG:-True}"
export FLASK_PORT="${FLASK_PORT:-5001}"
export FLASK_HOST="${FLASK_HOST:-0.0.0.0}"

echo ""
echo "${BOLD}Server Configuration:${NC}"
echo "  ${MAGENTA}•${NC} Debug Mode:  ${GREEN}${BOLD}Enabled${NC}"
echo "  ${MAGENTA}•${NC} Host:        ${FLASK_HOST}"
echo "  ${MAGENTA}•${NC} Port:        ${FLASK_PORT}"
echo "  ${MAGENTA}•${NC} Auto-reload: ${GREEN}Enabled${NC}"
echo ""

echo "${BOLD}Access URLs:${NC}"
echo "  ${CYAN}•${NC} Home:         http://127.0.0.1:${FLASK_PORT}/"
echo "  ${CYAN}•${NC} Chat UI:      http://127.0.0.1:${FLASK_PORT}/traintraveladvisor"
echo "  ${CYAN}•${NC} Health:       http://127.0.0.1:${FLASK_PORT}/api/health"
if [[ "${FLASK_HOST}" != "127.0.0.1" && "${FLASK_HOST}" != "localhost" ]]; then
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
    if [[ -n "$LOCAL_IP" ]]; then
        echo "  ${CYAN}•${NC} Network:      http://${LOCAL_IP}:${FLASK_PORT}/"
    fi
fi
echo ""

echo "${BOLD}${YELLOW}⚠  Important Notes:${NC}"
echo "  ${YELLOW}•${NC} Debug mode is ${RED}NOT${NC} suitable for production"
echo "  ${YELLOW}•${NC} The server will auto-reload on code changes"
echo "  ${YELLOW}•${NC} Press ${BOLD}CTRL+C${NC} to stop the server"
echo ""

echo "${CYAN}────────────────────────────────────────────────────────────${NC}\n"

# Run the Flask application
echo "${GREEN}${BOLD}Starting development server...${NC}\n"

# Export environment variables and run
export FLASK_DEBUG FLASK_PORT FLASK_HOST
exec python app.py
