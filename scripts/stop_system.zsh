#!/bin/zsh
#
# Darwin Rail AI System Stop Script
# Gracefully stops all system components
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo "${RED}🛑 Stopping Darwin Rail AI System${NC}"
echo "${RED}===================================${NC}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Function to stop service by port
stop_service_by_port() {
    local service_name="$1"
    local port="$2"
    local description="$3"
    
    printf "🔍 Checking %-20s (port $port)... " "$service_name"
    
    if lsof -ti:$port >/dev/null 2>&1; then
        echo "${YELLOW}Found running${NC}"
        echo "   ${BLUE}Stopping $description...${NC}"
        
        # Get PIDs using the port
        local pids=$(lsof -ti:$port)
        
        # Try graceful shutdown first (SIGTERM)
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 2
        
        # Check if still running
        if lsof -ti:$port >/dev/null 2>&1; then
            echo "   ${YELLOW}⚠️  Graceful shutdown failed, forcing termination...${NC}"
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
        
        # Final check
        if lsof -ti:$port >/dev/null 2>&1; then
            echo "   ${RED}❌ Failed to stop service on port $port${NC}"
            return 1
        else
            echo "   ${GREEN}✅ Stopped successfully${NC}"
            
            # Remove PID file if exists
            if [[ -f "logs/${service_name}.pid" ]]; then
                rm -f "logs/${service_name}.pid"
            fi
        fi
    else
        echo "${GRAY}Not running${NC}"
    fi
}

# Function to stop service by process name
stop_service_by_process() {
    local service_name="$1"
    local script_name="$2"
    local description="$3"
    
    printf "🔍 Checking %-20s (process)... " "$service_name"
    
    if pgrep -f "$script_name" >/dev/null 2>&1; then
        echo "${YELLOW}Found running${NC}"
        echo "   ${BLUE}Stopping $description...${NC}"
        
        # Get PIDs
        local pids=$(pgrep -f "$script_name")
        
        # Try graceful shutdown first (SIGTERM)
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 2
        
        # Check if still running
        if pgrep -f "$script_name" >/dev/null 2>&1; then
            echo "   ${YELLOW}⚠️  Graceful shutdown failed, forcing termination...${NC}"
            pkill -9 -f "$script_name" 2>/dev/null || true
            sleep 1
        fi
        
        # Final check
        if pgrep -f "$script_name" >/dev/null 2>&1; then
            echo "   ${RED}❌ Failed to stop $script_name${NC}"
            return 1
        else
            echo "   ${GREEN}✅ Stopped successfully${NC}"
            
            # Remove PID file if exists
            if [[ -f "logs/${service_name}.pid" ]]; then
                rm -f "logs/${service_name}.pid"
            fi
        fi
    else
        echo "${GRAY}Not running${NC}"
    fi
}

echo
echo "${BLUE}🛑 Stopping system components...${NC}"
echo

# Stop services in reverse order (passenger services first, then core)
echo "${BLUE}Phase 1: Stopping Passenger Services${NC}"
stop_service_by_port "passenger_portal" "5006" "Web passenger interface"
stop_service_by_port "station_displays" "5005" "Enhanced departure boards"
stop_service_by_port "alternative_routing" "5004" "Route planning engine"
stop_service_by_port "smart_notifications" "5003" "Intelligent passenger alerts"
stop_service_by_port "mobile_api" "5002" "Mobile app interface"

echo
echo "${BLUE}Phase 2: Stopping Core Processing Services${NC}"
stop_service_by_process "live_integration" "live_integration.py" "Darwin live feed processing"
stop_service_by_port "enhanced_api" "8080" "Core enrichment API & dashboard"

echo
echo "${BLUE}🧹 Cleanup tasks...${NC}"

# Clean up any remaining Python processes related to the project
echo "🔍 Checking for orphaned Python processes..."
orphaned_pids=$(ps aux | grep python | grep -E "(enhanced_api|live_integration|mobile_api|smart_notifications|alternative_routing|station_displays|passenger_portal)" | grep -v grep | awk '{print $2}' 2>/dev/null || true)

if [[ -n "$orphaned_pids" ]]; then
    echo "   ${YELLOW}Found orphaned processes: $orphaned_pids${NC}"
    echo "   ${BLUE}Cleaning up orphaned processes...${NC}"
    echo "$orphaned_pids" | xargs kill 2>/dev/null || true
    sleep 1
    echo "$orphaned_pids" | xargs kill -9 2>/dev/null || true
    echo "   ${GREEN}✅ Cleanup complete${NC}"
else
    echo "   ${GREEN}✅ No orphaned processes found${NC}"
fi

# Check for any remaining processes on our ports
echo "🔍 Final port check..."
remaining_ports=""
for port in 8080 5002 5003 5004 5005 5006; do
    if lsof -i:$port >/dev/null 2>&1; then
        remaining_ports="$remaining_ports $port"
    fi
done

if [[ -n "$remaining_ports" ]]; then
    echo "   ${YELLOW}⚠️  Ports still in use:$remaining_ports${NC}"
    echo "   ${GRAY}These may be used by other applications${NC}"
else
    echo "   ${GREEN}✅ All target ports are free${NC}"
fi

echo
echo "${RED}🏁 System shutdown complete!${NC}"
echo "${RED}==============================${NC}"
echo
echo "${GRAY}💡 Usage:${NC}"
echo "${GRAY}   Start system:  ./scripts/start_system.zsh${NC}"
echo "${GRAY}   Check status:  ./scripts/system_status.zsh${NC}"
echo "${GRAY}   View logs:     ls -la logs/${NC}"
echo
echo "${GREEN}🎯 All Darwin Rail AI services have been stopped${NC}"