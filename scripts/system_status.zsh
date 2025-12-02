#!/bin/zsh
#
# Darwin Rail AI System Status Checker
# Checks if all system components are running and healthy
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo "${BLUE}🔍 Darwin Rail AI System Status Check${NC}"
echo "${BLUE}====================================${NC}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Function to check service status
check_service() {
    local service_name="$1"
    local port="$2"
    local endpoint="$3"
    local description="$4"
    
    printf "%-20s %-6s " "$service_name" "($port)"
    
    # Check if port is listening
    if lsof -i:$port >/dev/null 2>&1; then
        # Port is open, check if service responds
        if [[ -n "$endpoint" ]]; then
            response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:$port$endpoint" 2>/dev/null || echo "000")
            if [[ "$response" == "200" ]]; then
                printf "${GREEN}✅ HEALTHY${NC}   "
            else
                printf "${YELLOW}⚠️  DEGRADED${NC}  "
            fi
            printf "${GRAY}(HTTP $response)${NC}"
        else
            printf "${GREEN}✅ RUNNING${NC}    "
            printf "${GRAY}(Process active)${NC}"
        fi
    else
        printf "${RED}❌ DOWN${NC}      "
        printf "${GRAY}(Port not listening)${NC}"
    fi
    
    echo "  $description"
}

# Function to check process by script name
check_process() {
    local service_name="$1"
    local script_name="$2"
    local description="$3"
    
    printf "%-20s %-6s " "$service_name" "(proc)"
    
    if pgrep -f "$script_name" >/dev/null; then
        printf "${GREEN}✅ RUNNING${NC}    "
        local pid=$(pgrep -f "$script_name" | head -1)
        printf "${GRAY}(PID: $pid)${NC}"
    else
        printf "${RED}❌ DOWN${NC}      "
        printf "${GRAY}(Process not found)${NC}"
    fi
    
    echo "  $description"
}

echo
echo "${BLUE}🌐 Service Status:${NC}"
echo "Service              Port   Status      Details"
echo "─────────────────────────────────────────────────────────────────"

# Check all services
check_service "Enhanced API" "8080" "/health" "Core enrichment API"
check_process "Live Integration" "live_integration.py" "Darwin feed processing"
check_service "Mobile API" "5002" "/mobile/v1/status" "Mobile app interface"
check_service "Smart Notifications" "5003" "/notifications/v1/status" "Intelligent alerts"
check_service "Alternative Routing" "5004" "" "Route planning engine"
check_service "Station Displays" "5005" "/display/v1/status" "Enhanced departure boards"
check_service "Passenger Portal" "5006" "/health" "Web passenger interface"

echo
echo "${BLUE}📊 System Overview:${NC}"

# Count services
total_ports=(8080 5002 5003 5004 5005 5006)
running_count=0
healthy_count=0

for port in "${total_ports[@]}"; do
    if lsof -i:$port >/dev/null 2>&1; then
        ((running_count++))
        
        # Test health endpoints where available
        case $port in
            8080)
                response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:8080/health" 2>/dev/null || echo "000")
                ;;
            5002)
                response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:5002/mobile/v1/status" 2>/dev/null || echo "000")
                ;;
            5003)
                response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:5003/notifications/v1/status" 2>/dev/null || echo "000")
                ;;
            5005)
                response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:5005/display/v1/status" 2>/dev/null || echo "000")
                ;;
            5006)
                response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:5006/health" 2>/dev/null || echo "000")
                ;;
            *)
                response="200"  # Assume healthy for services without health endpoints
                ;;
        esac
        
        if [[ "$response" == "200" ]]; then
            ((healthy_count++))
        fi
    fi
done

# Check live integration separately
if pgrep -f "live_integration.py" >/dev/null; then
    ((running_count++))
    ((healthy_count++))
fi

total_services=7

echo "📈 Services Running: ${GREEN}$running_count/$total_services${NC}"
echo "💚 Services Healthy: ${GREEN}$healthy_count/$total_services${NC}"

if [[ $running_count -eq $total_services ]] && [[ $healthy_count -eq $total_services ]]; then
    echo "🎉 ${GREEN}System Status: ALL SYSTEMS OPERATIONAL${NC}"
    exit_code=0
elif [[ $running_count -gt 0 ]]; then
    echo "⚠️  ${YELLOW}System Status: PARTIALLY OPERATIONAL${NC}"
    exit_code=1
else
    echo "🚨 ${RED}System Status: SYSTEM DOWN${NC}"
    exit_code=2
fi

echo
echo "${BLUE}🔗 Quick Access URLs:${NC}"
if lsof -i:8080 >/dev/null 2>&1; then
    echo "📊 Enhanced API Dashboard: ${BLUE}http://localhost:8080/cancellations/dashboard${NC}"
fi
if lsof -i:5006 >/dev/null 2>&1; then
    echo "🏠 Passenger Portal:      ${BLUE}http://localhost:5006${NC}"
fi

echo
echo "${GRAY}💡 Usage:${NC}"
echo "${GRAY}   Start system: ./scripts/start_system.zsh${NC}"
echo "${GRAY}   View logs:    tail -f logs/<service_name>.log${NC}"
echo "${GRAY}   Stop system:  ./scripts/stop_system.zsh${NC}"

exit $exit_code