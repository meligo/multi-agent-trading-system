# Background Services - Quick Start Guide

Run the entire trading system in the background with zero console noise!

## Quick Commands

```bash
# Start everything (runs in background)
./service_manager.sh start

# Check status
./service_manager.sh status

# View logs in real-time
./service_manager.sh logs

# Stop everything
./service_manager.sh stop

# Restart all services
./service_manager.sh restart

# Clean old processes
./service_manager.sh clean
```

## What Gets Started

When you run `./service_manager.sh start`, it launches:

1. **DataHub Server** - Centralized data streaming hub
2. **WebSocket Collector** - Real-time market data collection
3. **DataBento Client** - CME futures data (real volume)
4. **Streamlit Dashboard** - Web UI on http://localhost:8505

All services run in the background with output redirected to log files.

## Log Files

All logs are saved to the `logs/` directory:

```
logs/
├── datahub.log          # DataHub server logs
├── websocket.log        # WebSocket collector logs
├── databento.log        # DataBento client logs
├── dashboard.log        # Streamlit dashboard logs
├── scalping_engine.log  # Trading engine logs
├── news_gating.log      # News gating service logs
├── ig_client.log        # IG Markets API logs
└── insightsentry.log    # InsightSentry API logs
```

### Viewing Logs

**Tail all logs in real-time:**
```bash
./service_manager.sh logs
```

**View specific log:**
```bash
tail -f logs/scalping_engine.log
tail -f logs/ig_client.log
```

**Search logs:**
```bash
grep "TRADE EXECUTED" logs/scalping_engine.log
grep "ERROR" logs/*.log
```

**View last 50 lines:**
```bash
tail -50 logs/dashboard.log
```

## Service Status

Check if services are running:

```bash
./service_manager.sh status
```

Example output:
```
==========================================
  Service Status
==========================================

✅ datahub is running (PID: 12345, Uptime: 1:23:45, Mem: 45.2MB)
✅ websocket is running (PID: 12346, Uptime: 1:23:43, Mem: 78.5MB)
✅ databento is running (PID: 12347, Uptime: 1:23:41, Mem: 32.1MB)
✅ dashboard is running (PID: 12348, Uptime: 1:23:39, Mem: 156.8MB)

Dashboard URL: http://localhost:8505
Logs directory: /Users/meligo/multi-agent-trading-system/logs
```

## Process Management

**PID Files:**
All process IDs are stored in `.pids/` directory:
```
.pids/
├── datahub.pid
├── websocket.pid
├── databento.pid
└── dashboard.pid
```

**Clean Orphaned Processes:**
If services crash or hang:
```bash
./service_manager.sh clean
```

This kills all related Python processes and cleans up PID files.

## Typical Workflow

### Morning Startup
```bash
cd /Users/meligo/multi-agent-trading-system

# Clean any old processes
./service_manager.sh clean

# Start everything
./service_manager.sh start

# Check status
./service_manager.sh status

# Open dashboard
open http://localhost:8505
```

### During Trading
```bash
# Monitor logs in real-time
./service_manager.sh logs

# Or watch specific logs
tail -f logs/scalping_engine.log | grep "TRADE"
```

### Evening Shutdown
```bash
# Stop all services
./service_manager.sh stop

# Verify everything stopped
./service_manager.sh status
```

## Log Rotation

Logs are automatically rotated when they reach 10 MB:
- Maximum file size: 10 MB
- Backup files: 5 (e.g., `scalping_engine.log.1`, `.log.2`, etc.)
- Total max storage per service: ~50 MB

## Troubleshooting

### Service Won't Start

1. Check logs for errors:
   ```bash
   tail -50 logs/[service_name].log
   ```

2. Check if port is already in use:
   ```bash
   lsof -i :8505  # Dashboard port
   ```

3. Clean and restart:
   ```bash
   ./service_manager.sh clean
   ./service_manager.sh start
   ```

### Service Crashed

Check the service log:
```bash
tail -100 logs/[service_name].log | grep -i error
```

Restart specific service:
```bash
./service_manager.sh stop
./service_manager.sh start
```

### Dashboard Not Loading

1. Check if running:
   ```bash
   ./service_manager.sh status
   ```

2. Check logs:
   ```bash
   tail -50 logs/dashboard.log
   ```

3. Restart dashboard:
   ```bash
   pkill -f scalping_dashboard
   ./service_manager.sh start
   ```

## Advanced Usage

### Run Only Specific Service

```bash
# Start just the dashboard
cd /Users/meligo/multi-agent-trading-system
nohup streamlit run scalping_dashboard.py > logs/dashboard.log 2>&1 &
```

### Custom Log Viewing

```bash
# Watch for trades
tail -f logs/scalping_engine.log | grep -E "TRADE EXECUTED|IG Order"

# Monitor errors only
tail -f logs/*.log | grep -i error

# See recent activity
for log in logs/*.log; do
    echo "=== $log ==="
    tail -5 "$log"
    echo ""
done
```

### Kill Everything (Emergency)

```bash
pkill -f "start_datahub_server.py"
pkill -f "websocket_collector_modern.py"
pkill -f "start_databento_client.py"
pkill -f "scalping_dashboard.py"
rm -f .pids/*.pid
```

## Benefits of Background Mode

✅ **Clean Console** - No log spam in terminal
✅ **Persistent Logs** - All output saved to files
✅ **Easy Management** - Simple start/stop/status commands
✅ **Log Rotation** - Automatic cleanup of old logs
✅ **Process Tracking** - PID files for reliable control
✅ **Crash Recovery** - Easy to identify and restart failed services

## Integration with System Startup (Optional)

### macOS (launchd)

Create `~/Library/LaunchAgents/com.trading.scalper.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.scalper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/meligo/multi-agent-trading-system/service_manager.sh</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/meligo/multi-agent-trading-system/logs/startup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/meligo/multi-agent-trading-system/logs/startup_error.log</string>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.trading.scalper.plist
```

### Linux (systemd)

Create `/etc/systemd/system/scalper.service`:

```ini
[Unit]
Description=Multi-Agent Trading System
After=network.target

[Service]
Type=forking
User=meligo
WorkingDirectory=/Users/meligo/multi-agent-trading-system
ExecStart=/Users/meligo/multi-agent-trading-system/service_manager.sh start
ExecStop=/Users/meligo/multi-agent-trading-system/service_manager.sh stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable scalper
sudo systemctl start scalper
```

---

**Status**: ✅ Ready to Use
**Version**: 1.0
**Last Updated**: 2025-11-04
