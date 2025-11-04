#!/bin/bash
#
# Service Manager for Multi-Agent Trading System
# Manages all background services with simple commands
#
# Usage:
#   ./service_manager.sh start    - Start all services
#   ./service_manager.sh stop     - Stop all services
#   ./service_manager.sh restart  - Restart all services
#   ./service_manager.sh status   - Check status of all services
#   ./service_manager.sh logs     - Tail all log files
#   ./service_manager.sh clean    - Clean old processes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_DIR="${PROJECT_DIR}/.pids"
LOG_DIR="${PROJECT_DIR}/logs"

# Create directories
mkdir -p "${PID_DIR}"
mkdir -p "${LOG_DIR}"

# Service definitions (bash 3.2 compatible)
SERVICES="datahub websocket databento scalper dashboard"

get_service_command() {
    case "$1" in
        datahub)
            echo "python -u start_datahub_server.py"
            ;;
        websocket)
            echo "python -u websocket_collector_modern.py"
            ;;
        databento)
            echo "python -u start_databento_client.py"
            ;;
        scalper)
            echo "python -u scalping_cli.py --run"
            ;;
        dashboard)
            echo "streamlit run scalping_dashboard.py --server.headless true"
            ;;
    esac
}

# Print colored message
print_msg() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if service is running
is_running() {
    local service=$1
    local pid_file="${PID_DIR}/${service}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            rm -f "$pid_file"  # Clean up stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Start a service
start_service() {
    local service=$1
    local command=$(get_service_command "$service")
    local pid_file="${PID_DIR}/${service}.pid"
    local log_file="${LOG_DIR}/${service}.log"

    if is_running "$service"; then
        print_msg "$YELLOW" "⚠️  $service is already running (PID: $(cat $pid_file))"
        return 0
    fi

    print_msg "$BLUE" "🚀 Starting $service..."

    # Start service in background and save PID
    cd "$PROJECT_DIR"
    nohup $command > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"

    # Wait a moment and check if it's still running
    sleep 2
    if is_running "$service"; then
        print_msg "$GREEN" "✅ $service started successfully (PID: $pid)"
        return 0
    else
        print_msg "$RED" "❌ $service failed to start"
        rm -f "$pid_file"
        print_msg "$YELLOW" "   Last 10 lines of log:"
        tail -10 "$log_file" | sed 's/^/   /'
        return 1
    fi
}

# Stop a service
stop_service() {
    local service=$1
    local pid_file="${PID_DIR}/${service}.pid"

    if ! is_running "$service"; then
        print_msg "$YELLOW" "⚠️  $service is not running"
        return 0
    fi

    local pid=$(cat "$pid_file")
    print_msg "$BLUE" "🛑 Stopping $service (PID: $pid)..."

    # Send SIGTERM
    kill "$pid" 2>/dev/null || true

    # Wait for graceful shutdown (max 10 seconds)
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        print_msg "$YELLOW" "   Force killing $service..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    print_msg "$GREEN" "✅ $service stopped"
}

# Show service status
service_status() {
    local service=$1
    local pid_file="${PID_DIR}/${service}.pid"

    if is_running "$service"; then
        local pid=$(cat "$pid_file")
        local uptime=$(ps -o etime= -p "$pid" | tr -d ' ')
        local mem=$(ps -o rss= -p "$pid" | awk '{printf "%.1fMB", $1/1024}')
        print_msg "$GREEN" "✅ $service is running (PID: $pid, Uptime: $uptime, Mem: $mem)"
    else
        print_msg "$RED" "❌ $service is not running"
    fi
}

# Start all services
start_all() {
    print_msg "$BLUE" "=========================================="
    print_msg "$BLUE" "  Starting All Services"
    print_msg "$BLUE" "=========================================="
    echo ""

    # Start in dependency order
    for service in $SERVICES; do
        start_service "$service"
        sleep 2
    done

    echo ""
    print_msg "$GREEN" "🎉 All services started!"
    echo ""
    print_msg "$BLUE" "Dashboard URL: http://localhost:8505"
    print_msg "$BLUE" "Logs directory: $LOG_DIR"
    echo ""
}

# Stop all services
stop_all() {
    print_msg "$BLUE" "=========================================="
    print_msg "$BLUE" "  Stopping All Services"
    print_msg "$BLUE" "=========================================="
    echo ""

    # Stop in reverse order (bash 3.2 compatible)
    local services_reverse=""
    for service in $SERVICES; do
        services_reverse="$service $services_reverse"
    done
    for service in $services_reverse; do
        stop_service "$service"
    done

    echo ""
    print_msg "$GREEN" "🎉 All services stopped!"
    echo ""
}

# Show status of all services
status_all() {
    print_msg "$BLUE" "=========================================="
    print_msg "$BLUE" "  Service Status"
    print_msg "$BLUE" "=========================================="
    echo ""

    for service in $SERVICES; do
        service_status "$service"
    done

    echo ""
    print_msg "$BLUE" "Dashboard URL: http://localhost:8505"
    print_msg "$BLUE" "Logs directory: $LOG_DIR"
    echo ""
}

# Tail all log files
tail_logs() {
    print_msg "$BLUE" "Tailing all log files (Ctrl+C to stop)..."
    echo ""
    tail -f "${LOG_DIR}"/*.log
}

# Clean old processes
clean_processes() {
    print_msg "$BLUE" "🧹 Cleaning old processes..."

    # Kill any orphaned Python processes
    pkill -f "start_datahub_server.py" 2>/dev/null || true
    pkill -f "websocket_collector_modern.py" 2>/dev/null || true
    pkill -f "start_databento_client.py" 2>/dev/null || true
    pkill -f "scalping_dashboard.py" 2>/dev/null || true

    # Clean PID files
    rm -f "${PID_DIR}"/*.pid

    print_msg "$GREEN" "✅ Cleanup complete"
}

# Main command handler
case "${1:-}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    status)
        status_all
        ;;
    logs)
        tail_logs
        ;;
    clean)
        clean_processes
        ;;
    *)
        echo "Multi-Agent Trading System - Service Manager"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|clean}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services in background"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Check status of all services"
        echo "  logs     - Tail all log files"
        echo "  clean    - Clean old processes and PID files"
        echo ""
        exit 1
        ;;
esac

exit 0
