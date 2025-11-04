# WSL Dashboard Access Fix

## Problem

Services are running in WSL, but you can't access the Streamlit dashboard from your Windows browser at `http://localhost:8505`.

## Root Cause

WSL has its own network interface. Streamlit might be:
1. Binding to `127.0.0.1` (WSL internal only)
2. Not accessible from Windows due to network isolation
3. Firewall blocking the connection

---

## ✅ Solutions (Try in Order)

### Solution 1: Access via localhost (Simplest)

**In Windows Browser:**
Try these URLs in order:
```
http://localhost:8505
http://127.0.0.1:8505
http://0.0.0.0:8505
```

**If none work**, Windows can't reach WSL's network. Continue to Solution 2.

---

### Solution 2: Get WSL IP Address

**Step 1: Find WSL IP**

In WSL terminal:
```bash
hostname -I | awk '{print $1}'
```

Example output: `172.20.10.5`

**Step 2: Access Dashboard**

In Windows browser:
```
http://172.20.10.5:8505
```
(Replace with your actual IP)

**If this works**: Bookmark this URL, but note it may change after reboot.

---

### Solution 3: Configure Streamlit to Bind to 0.0.0.0

This makes the dashboard accessible from Windows.

**Step 1: Check Current Streamlit Command**

In WSL:
```bash
ps aux | grep streamlit
```

Look for something like:
```
streamlit run dashboard_v2.py --server.port 8505
```

**Step 2: Stop Services**

```bash
./service_manager.sh stop all
```

**Step 3: Create Streamlit Config**

Create `.streamlit/config.toml`:
```bash
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << 'EOF'
[server]
port = 8505
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false
EOF
```

**Step 4: Restart Services**

```bash
./service_manager.sh start all
```

**Step 5: Test**

In Windows browser:
```
http://localhost:8505
```

Should now work! ✅

---

### Solution 4: Port Forwarding (WSL 1 Only)

**Check WSL Version:**
```bash
wsl --list --verbose
```

If you see `VERSION 1`, use port forwarding.

**In Windows PowerShell (as Administrator):**
```powershell
# Get WSL IP
$wslIp = (wsl hostname -I).Trim()

# Forward port 8505
netsh interface portproxy add v4tov4 listenport=8505 listenaddress=0.0.0.0 connectport=8505 connectaddress=$wslIp

# Verify
netsh interface portproxy show all
```

**Access:**
```
http://localhost:8505
```

---

### Solution 5: Windows Firewall Exception

**In Windows PowerShell (as Administrator):**
```powershell
# Allow inbound on port 8505
New-NetFirewallRule -DisplayName "Streamlit Dashboard" -Direction Inbound -LocalPort 8505 -Protocol TCP -Action Allow
```

---

## 🔍 Debugging Commands

### Check if Dashboard is Running

**In WSL:**
```bash
# Check process
ps aux | grep streamlit

# Check port
netstat -tuln | grep 8505

# Alternative
lsof -i :8505

# Check logs
tail -f logs/dashboard.log
```

### Check WSL Network

**In WSL:**
```bash
# Show all IPs
hostname -I

# Show network interfaces
ip addr show

# Test local access
curl http://localhost:8505
```

### Check from Windows

**In Windows PowerShell:**
```powershell
# Test connection
Test-NetConnection -ComputerName localhost -Port 8505

# Show listening ports
netstat -an | findstr :8505
```

---

## 🎯 Recommended Setup

**Create a custom Streamlit start script:**

`start_dashboard_wsl.sh`:
```bash
#!/bin/bash
# Start Streamlit with WSL-compatible settings

echo "🚀 Starting Streamlit dashboard (WSL mode)..."

# Get WSL IP for display
WSL_IP=$(hostname -I | awk '{print $1}')

# Start Streamlit bound to all interfaces
streamlit run dashboard_v2.py \
    --server.port 8505 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    > logs/dashboard.log 2>&1 &

# Wait for startup
sleep 3

# Display access URLs
echo ""
echo "✅ Dashboard started!"
echo ""
echo "Access from Windows browser:"
echo "  🌐 http://localhost:8505"
echo "  🌐 http://$WSL_IP:8505"
echo ""
echo "Logs: tail -f logs/dashboard.log"
```

**Make executable and run:**
```bash
chmod +x start_dashboard_wsl.sh
./start_dashboard_wsl.sh
```

---

## 🆘 Still Not Working?

### Check Service Manager

Your `service_manager.sh` might not be binding Streamlit correctly.

**Find the Streamlit start command:**
```bash
cat service_manager.sh | grep streamlit
```

**Should look like:**
```bash
streamlit run dashboard_v2.py --server.port 8505 --server.address 0.0.0.0
```

**If it's missing `--server.address 0.0.0.0`**, add it.

### Manual Dashboard Start

Stop services and start dashboard manually:
```bash
./service_manager.sh stop all

# Start only dashboard with explicit binding
streamlit run dashboard_v2.py \
    --server.port 8505 \
    --server.address 0.0.0.0 \
    --server.headless true

# Keep terminal open, check output
```

Then try `http://localhost:8505` in Windows browser.

---

## 📋 Quick Checklist

- [ ] Services running in WSL: `./service_manager.sh status`
- [ ] Dashboard process exists: `ps aux | grep streamlit`
- [ ] Port 8505 listening: `netstat -tuln | grep 8505`
- [ ] Tried `http://localhost:8505` in Windows browser
- [ ] Tried `http://127.0.0.1:8505` in Windows browser
- [ ] Got WSL IP: `hostname -I`
- [ ] Tried `http://<WSL-IP>:8505` in Windows browser
- [ ] Created Streamlit config with `address = "0.0.0.0"`
- [ ] Checked firewall: Windows Security → Firewall
- [ ] Dashboard logs: `tail -f logs/dashboard.log`

---

## ✅ Success Indicators

When working, you should see:

**In WSL terminal:**
```
✅ dashboard started successfully (PID: 12345)
Dashboard URL: http://localhost:8505
```

**In Windows browser:**
Streamlit dashboard loads showing:
- Real-time spreads
- Candle data
- Trading signals
- System status

---

## 💡 Pro Tips

1. **Bookmark with IP**: If `localhost` doesn't work, use the WSL IP and bookmark it
   ```
   http://172.20.10.5:8505
   ```

2. **Auto-start on boot**: Add to Windows Task Scheduler
   ```
   wsl -d Ubuntu -e bash -c "cd ~/multi-agent-trading-system && ./service_manager.sh start all"
   ```

3. **Access from phone**: Use WSL IP to access from phone on same network
   ```
   http://172.20.10.5:8505
   ```

4. **Check WSL version**: WSL 2 has better networking
   ```bash
   wsl --list --verbose
   ```

---

## 🔧 If All Else Fails

**Run dashboard directly in Windows (not WSL):**

In Windows PowerShell:
```powershell
cd H:\Repo\multi-agent-trading-system\multi-agent-trading-system
.\.venv\Scripts\Activate.ps1
streamlit run dashboard_v2.py --server.port 8505
```

This bypasses WSL networking entirely.

---

**Last Updated**: November 2025
**Applies To**: WSL 1 and WSL 2 on Windows 11
