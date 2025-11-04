# Windows 11 Quick Start Guide

## 🚀 Fastest Method: WSL (Recommended)

### 1. Install WSL (5 minutes)

**Open PowerShell as Administrator** and run:
```powershell
wsl --install
```

**Restart your computer**.

### 2. Setup Ubuntu (10 minutes)

Open **Ubuntu** from Start Menu, then:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install everything needed
sudo apt install python3.11 python3.11-venv python3-pip postgresql git -y

# Navigate to your project (adjust YourUsername)
cd /mnt/c/Users/YourUsername/Desktop/multi-agent-trading-system

# Setup Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup PostgreSQL
sudo service postgresql start
sudo -u postgres psql -c "CREATE DATABASE forex_scalping;"
sudo -u postgres psql -d forex_scalping -f database_setup.sql

# Configure your credentials
cp .env.example .env
nano .env  # Edit with your IG credentials
```

### 3. Start Trading System

```bash
# Make script executable
chmod +x service_manager.sh

# Start all services
./service_manager.sh start all

# Check status
./service_manager.sh status

# Watch progress (wait for 30 candles)
tail -f logs/scalping_engine.log | grep "candles"
```

### 4. Access Dashboard

Open browser: **http://localhost:8505**

Done! 🎉

---

## 🪟 Alternative: Native Windows (No WSL)

### Option A: PowerShell Script (Best)

```powershell
# In PowerShell:
.\service_manager.ps1 start all
.\service_manager.ps1 stop all
.\service_manager.ps1 status
```

### Option B: Batch Script

```cmd
REM In Command Prompt:
service_manager.bat start all
service_manager.bat stop all
service_manager.bat status
```

### Option C: Git Bash

```bash
# In Git Bash:
./service_manager.sh start all
```

---

## 📋 Prerequisites for Native Windows

### 1. Python 3.11+
- Download: https://www.python.org/downloads/
- ✅ Check "Add Python to PATH"

### 2. PostgreSQL
- Download: https://www.postgresql.org/download/windows/
- Remember your password!

### 3. Virtual Environment
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Environment Variables

**Quick Setup (PowerShell as Admin):**
```powershell
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql://postgres:yourpassword@localhost:5432/forex_scalping', 'User')
[System.Environment]::SetEnvironmentVariable('IG_USERNAME', 'your_username', 'User')
[System.Environment]::SetEnvironmentVariable('IG_PASSWORD', 'your_password', 'User')
[System.Environment]::SetEnvironmentVariable('IG_API_KEY', 'your_api_key', 'User')
```

**Or Manual:**
1. Press `Win + X` → System
2. Advanced system settings → Environment Variables
3. Add each variable under "User variables"

---

## 🔧 Common Commands

### WSL (Linux-style)
```bash
# Start services
./service_manager.sh start all

# Stop services
./service_manager.sh stop all

# Check status
./service_manager.sh status

# View logs
tail -f logs/scalping_engine.log
tail -f logs/websocket.log

# Check database
sudo -u postgres psql -d forex_scalping -c "SELECT COUNT(*) FROM ig_spot_ticks;"
```

### PowerShell (Windows-style)
```powershell
# Start services
.\service_manager.ps1 start all

# Stop services
.\service_manager.ps1 stop all

# Check status
.\service_manager.ps1 status

# View logs
Get-Content logs\scalping_engine.log -Tail 20 -Wait
Get-Content logs\websocket.log -Tail 20 -Wait

# Check database
psql -U postgres -d forex_scalping -c "SELECT COUNT(*) FROM ig_spot_ticks;"
```

---

## 🐛 Troubleshooting

### "wsl: command not found"
```powershell
# Enable WSL (PowerShell as Admin)
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
# Restart computer
```

### "python: command not found" (WSL)
```bash
sudo apt install python3.11 python3.11-venv python3-pip
```

### "Access Denied" running PowerShell script
```powershell
# Allow scripts (PowerShell as Admin)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port 8505 already in use
```powershell
# Find process
netstat -ano | findstr :8505

# Kill process (replace 1234 with PID)
taskkill /PID 1234 /F
```

### PostgreSQL won't start (WSL)
```bash
# Check status
sudo service postgresql status

# Start manually
sudo service postgresql start

# If it fails, reinitialize
sudo pg_ctlcluster 14 main start
```

### Services won't stop (Windows)
```powershell
# Kill all Python processes
taskkill /F /IM python.exe
taskkill /F /IM streamlit.exe
```

---

## 📊 Monitoring Progress

### Check Candle Accumulation

**WSL/Git Bash:**
```bash
# Watch real-time progress
tail -f logs/scalping_engine.log | grep "candles"

# You'll see:
# ⚠️  Insufficient data for EUR_USD (5/30 candles - need 25 more)
# ⚠️  Insufficient data for EUR_USD (10/30 candles - need 20 more)
# ...
# ✅ All pre-trade gates PASSED for EUR_USD
```

**PowerShell:**
```powershell
Get-Content logs\scalping_engine.log -Tail 20 -Wait | Select-String "candles"
```

### Expected Timeline
- **0-5 minutes**: Services starting, IG connection established
- **5-30 minutes**: Data accumulation (need 30 candles)
- **30+ minutes**: Trading system active, analyzing setups

---

## 🎯 Success Indicators

✅ **All services running**
```bash
./service_manager.sh status
# Should show all services as RUNNING
```

✅ **Data being collected**
```bash
# Database should have thousands of ticks
psql -U postgres -d forex_scalping -c "SELECT COUNT(*) FROM ig_spot_ticks;"
```

✅ **Dashboard accessible**
```
Open http://localhost:8505
Should show live spreads and candle data
```

✅ **Logs show progress**
```bash
tail -20 logs/scalping_engine.log
# Should show: "Analyzing EUR_USD" every 60 seconds
# Should show: "(X/30 candles - need Y more)"
```

---

## 💡 Tips for Windows Users

1. **Use WSL** - Best compatibility, no modifications needed
2. **Store project in WSL** - Better I/O performance than `/mnt/c/`
3. **PowerShell > CMD** - More powerful, better error handling
4. **Add aliases** (PowerShell profile):
   ```powershell
   notepad $PROFILE
   # Add:
   function logs { Get-Content logs\scalping_engine.log -Tail 20 -Wait }
   function start-trader { .\service_manager.ps1 start all }
   function stop-trader { .\service_manager.ps1 stop all }
   ```

5. **Pin Ubuntu to taskbar** - Quick access to WSL terminal

---

## 📚 Next Steps

After services are running:

1. **Wait 30 minutes** for sufficient data (30 candles)
2. **Monitor logs** to see data accumulation progress
3. **Check dashboard** at http://localhost:8505
4. **Review trades** when system starts analyzing (logs will show "All pre-trade gates PASSED")
5. **Verify database** is saving all data persistently

---

## 🆘 Need Help?

- **Full documentation**: See `WINDOWS_SETUP.md`
- **WSL guide**: https://learn.microsoft.com/en-us/windows/wsl/
- **PostgreSQL Windows**: https://www.postgresql.org/docs/
- **Check logs**: Always check `logs/` directory for error messages

---

**Version**: 1.0
**Last Updated**: January 2025
**Compatibility**: Windows 11, WSL2, PowerShell 5.1+
