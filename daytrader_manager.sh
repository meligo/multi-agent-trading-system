#!/bin/bash
# ==========================================
#  Multi-Agent Trading System - Service Manager
#  Main Branch
# ==========================================

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directories
LOGS_DIR="logs"
PIDS_DIR="pids"

# Create directories if they don't exist
mkdir -p "$LOGS_DIR"
mkdir -p "$PIDS_DIR"

# Service definitions
declare -A SERVICES=(
    ["worker"]="ig_concurrent_worker.py"
    ["dashboard"]="ig_trading_dashboard.py"
    ["monitor"]="position_monitor.py"
    ["websocket"]="websocket_collector.py"
)

declare -A SERVICE_DESCRIPTIONS=(
    ["worker"]="Trading Worker (Main Analysis Engine)"
    ["dashboard"]="Trading Dashboard (Streamlit on port 8501)"
    ["monitor"]="Position Monitor (Trade Management)"
    ["websocket"]="WebSocket Collector (Real-time Data)"
)

# ==========================================
#  Helper Functions
# ==========================================

print_header() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}🔵 $1${NC}"
}

# ==========================================
#  Service Management Functions
# ==========================================

start_service() {
    local service_name="$1"
    local script_name="${SERVICES[$service_name]}"
    local pid_file="$PIDS_DIR/${service_name}.pid"
    local log_file="$LOGS_DIR/${service_name}.log"

    # Check if already running
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            print_warning "${SERVICE_DESCRIPTIONS[$service_name]} already running (PID: $pid)"
            return 0
        else
            # Stale PID file
            rm -f "$pid_file"
        fi
    fi

    echo -e "${BLUE}🚀 Starting ${SERVICE_DESCRIPTIONS[$service_name]}...${NC}"

    # Special handling for dashboard (Streamlit)
    if [ "$service_name" == "dashboard" ]; then
        nohup streamlit run "$script_name" --server.port 8501 > "$log_file" 2>&1 &
    else
        nohup python -u "$script_name" > "$log_file" 2>&1 &
    fi

    local pid=$!
    echo $pid > "$pid_file"

    # Wait a moment and check if it started successfully
    sleep 2

    if ps -p $pid > /dev/null 2>&1; then
        print_success "${SERVICE_DESCRIPTIONS[$service_name]} started successfully (PID: $pid)"
    else
        print_error "${SERVICE_DESCRIPTIONS[$service_name]} failed to start"
        rm -f "$pid_file"
        return 1
    fi
}

stop_service() {
    local service_name="$1"
    local pid_file="$PIDS_DIR/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        print_warning "${SERVICE_DESCRIPTIONS[$service_name]} is not running (no PID file)"
        return 0
    fi

    local pid=$(cat "$pid_file")

    if ! ps -p $pid > /dev/null 2>&1; then
        print_warning "${SERVICE_DESCRIPTIONS[$service_name]} is not running (stale PID)"
        rm -f "$pid_file"
        return 0
    fi

    echo -e "${BLUE}🛑 Stopping ${SERVICE_DESCRIPTIONS[$service_name]} (PID: $pid)...${NC}"

    kill $pid

    # Wait for graceful shutdown
    local count=0
    while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p $pid > /dev/null 2>&1; then
        print_warning "Force killing process..."
        kill -9 $pid 2>/dev/null || true
    fi

    rm -f "$pid_file"
    print_success "${SERVICE_DESCRIPTIONS[$service_name]} stopped"
}

status_service() {
    local service_name="$1"
    local pid_file="$PIDS_DIR/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        echo -e "  ${SERVICE_DESCRIPTIONS[$service_name]}: ${RED}NOT RUNNING${NC}"
        return 1
    fi

    local pid=$(cat "$pid_file")

    if ps -p $pid > /dev/null 2>&1; then
        # Get process info
        local cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
        local mem=$(ps -p $pid -o %mem= | tr -d ' ')
        local etime=$(ps -p $pid -o etime= | tr -d ' ')

        echo -e "  ${SERVICE_DESCRIPTIONS[$service_name]}: ${GREEN}RUNNING${NC} (PID: $pid, CPU: ${cpu}%, MEM: ${mem}%, Time: $etime)"
        return 0
    else
        echo -e "  ${SERVICE_DESCRIPTIONS[$service_name]}: ${RED}NOT RUNNING${NC} (stale PID)"
        rm -f "$pid_file"
        return 1
    fi
}

# ==========================================
#  Main Commands
# ==========================================

start_all() {
    print_header "Starting All Services"

    # Start in dependency order
    start_service "websocket"
    sleep 2

    start_service "worker"
    sleep 2

    start_service "monitor"
    sleep 2

    start_service "dashboard"

    echo ""
    print_success "All services started!"
    echo -e "${BLUE}Dashboard URL: http://localhost:8501${NC}"
    echo -e "${BLUE}Logs directory: $LOGS_DIR${NC}"
    echo ""
}

stop_all() {
    print_header "Stopping All Services"

    # Stop in reverse order
    stop_service "dashboard"
    stop_service "monitor"
    stop_service "worker"
    stop_service "websocket"

    echo ""
    print_success "All services stopped!"
    echo ""
}

restart_all() {
    print_header "Restarting All Services"
    stop_all
    sleep 2
    start_all
}

show_status() {
    print_header "Service Status"

    for service in websocket worker monitor dashboard; do
        status_service "$service"
    done

    echo ""

    # Show recent log activity
    print_info "Recent Log Activity:"
    echo ""

    for service in worker monitor; do
        local log_file="$LOGS_DIR/${service}.log"
        if [ -f "$log_file" ]; then
            echo -e "${YELLOW}--- ${SERVICE_DESCRIPTIONS[$service]} (last 3 lines) ---${NC}"
            tail -n 3 "$log_file" 2>/dev/null || echo "No logs available"
            echo ""
        fi
    done
}

show_logs() {
    local service_name="$1"
    local log_file="$LOGS_DIR/${service_name}.log"

    if [ ! -f "$log_file" ]; then
        print_error "Log file not found: $log_file"
        return 1
    fi

    if [ -z "$2" ]; then
        # Follow logs
        echo -e "${BLUE}Following logs for ${SERVICE_DESCRIPTIONS[$service_name]}...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        echo ""
        tail -f "$log_file"
    else
        # Show last N lines
        local lines="$2"
        echo -e "${BLUE}Last $lines lines from ${SERVICE_DESCRIPTIONS[$service_name]}:${NC}"
        echo ""
        tail -n "$lines" "$log_file"
    fi
}

# ==========================================
#  Usage Information
# ==========================================

show_usage() {
    echo ""
    print_header "Multi-Agent Trading System - Service Manager"
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start [service|all]   Start service(s)"
    echo "  stop [service|all]    Stop service(s)"
    echo "  restart [service|all] Restart service(s)"
    echo "  status                Show status of all services"
    echo "  logs [service] [N]    Show logs (follow if N not specified)"
    echo ""
    echo "Services:"
    echo "  websocket            WebSocket Collector (real-time data)"
    echo "  worker               Trading Worker (main analysis)"
    echo "  monitor              Position Monitor (trade management)"
    echo "  dashboard            Trading Dashboard (Streamlit UI)"
    echo "  all                  All services"
    echo ""
    echo "Examples:"
    echo "  $0 start all         Start all services"
    echo "  $0 stop worker       Stop trading worker only"
    echo "  $0 restart dashboard Restart dashboard"
    echo "  $0 status            Show status of all services"
    echo "  $0 logs worker       Follow worker logs"
    echo "  $0 logs worker 50    Show last 50 lines of worker logs"
    echo ""
}

# ==========================================
#  Main Script Logic
# ==========================================

case "$1" in
    start)
        if [ "$2" == "all" ] || [ -z "$2" ]; then
            start_all
        elif [ -n "${SERVICES[$2]}" ]; then
            start_service "$2"
        else
            print_error "Unknown service: $2"
            show_usage
            exit 1
        fi
        ;;

    stop)
        if [ "$2" == "all" ] || [ -z "$2" ]; then
            stop_all
        elif [ -n "${SERVICES[$2]}" ]; then
            stop_service "$2"
        else
            print_error "Unknown service: $2"
            show_usage
            exit 1
        fi
        ;;

    restart)
        if [ "$2" == "all" ] || [ -z "$2" ]; then
            restart_all
        elif [ -n "${SERVICES[$2]}" ]; then
            stop_service "$2"
            sleep 2
            start_service "$2"
        else
            print_error "Unknown service: $2"
            show_usage
            exit 1
        fi
        ;;

    status)
        show_status
        ;;

    logs)
        if [ -z "$2" ]; then
            print_error "Please specify a service"
            show_usage
            exit 1
        elif [ -n "${SERVICES[$2]}" ]; then
            show_logs "$2" "$3"
        else
            print_error "Unknown service: $2"
            show_usage
            exit 1
        fi
        ;;

    *)
        show_usage
        exit 1
        ;;
esac
