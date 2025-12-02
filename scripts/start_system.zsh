#!/bin/zsh
#
# Darwin Rail AI System Startup Script
# Starts all system components in the correct order
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "${BLUE}🚀 Starting Darwin Rail AI System${NC}"
echo "${BLUE}========================================${NC}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "${GREEN}📁 Project root: $PROJECT_ROOT${NC}"

# Change to project directory
cd "$PROJECT_ROOT"

# Activate virtual environment
echo "${YELLOW}🔧 Activating virtual environment...${NC}"
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    echo "${GREEN}✅ Virtual environment activated${NC}"
else
    echo "${RED}❌ Virtual environment not found at .venv/bin/activate${NC}"
    exit 1
fi

# Function to start service in background
start_service() {
    local service_name="$1"
    local script_name="$2"
    local port="$3"
    local description="$4"
    
    echo "${YELLOW}🚀 Starting $service_name ($description)...${NC}"
    
    # Check if service is already running
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "${YELLOW}⚠️  Port $port already in use, killing existing process...${NC}"
        lsof -ti:$port | xargs kill -9 >/dev/null 2>&1 || true
        sleep 1
    fi
    
    # Start the service
    python "$script_name" > "logs/${service_name}.log" 2>&1 &
    local pid=$!
    
    # Wait a moment for startup
    sleep 2
    
    # Check if service started successfully
    if kill -0 $pid 2>/dev/null; then
        echo "${GREEN}✅ $service_name started successfully (PID: $pid)${NC}"
        echo "$pid" > "logs/${service_name}.pid"
    else
        echo "${RED}❌ Failed to start $service_name${NC}"
        return 1
    fi
}

# Create logs directory if it doesn't exist
mkdir -p logs

echo "${BLUE}📋 Starting system components...${NC}"
echo

# Start core services first
echo "${BLUE}Phase 1: Core Processing Services${NC}"
start_service "enhanced_api" "enhanced_api.py" "8080" "Core enrichment API & dashboard"
start_service "live_integration" "live_integration.py" "61613" "Darwin live feed processing"

echo
echo "${BLUE}Phase 2: Passenger Services${NC}"
start_service "mobile_api" "mobile_api.py" "5002" "Mobile app interface"
start_service "smart_notifications" "smart_notifications.py" "5003" "Intelligent passenger alerts"
start_service "alternative_routing" "alternative_routing.py" "5004" "Route planning engine"
start_service "station_displays" "station_displays.py" "5005" "Enhanced departure boards"
start_service "passenger_portal" "passenger_portal_simple.py" "5006" "Web passenger interface"

echo
echo "${BLUE}🎯 System startup complete!${NC}"
echo "${BLUE}========================================${NC}"
echo
echo "${GREEN}📊 Access Points:${NC}"
echo "🌐 Enhanced API Dashboard: ${BLUE}http://localhost:8080/cancellations/dashboard${NC}"
echo "📱 Mobile API Status:     ${BLUE}http://localhost:5002/mobile/v1/status${NC}"
echo "🔔 Smart Notifications:   ${BLUE}http://localhost:5003/notifications/v1/status${NC}"
echo "🛣️  Alternative Routing:   ${BLUE}http://localhost:5004/routing/v1/plan${NC}"
echo "📺 Station Displays:      ${BLUE}http://localhost:5005/display/v1/status${NC}"
echo "🏠 Passenger Portal:      ${BLUE}http://localhost:5006${NC}"
echo
echo "${GREEN}📁 Logs directory: ${PROJECT_ROOT}/logs${NC}"
echo "${GREEN}🔍 Check service logs: tail -f logs/<service_name>.log${NC}"
echo "${GREEN}🛑 Stop all services: ./scripts/stop_system.zsh${NC}"
echo
echo "${GREEN}🎉 Darwin Rail AI System is now running!${NC}"