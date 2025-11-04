# Running Multi-Agent Trading System on Windows 11

## Option 1: WSL (Windows Subsystem for Linux) - RECOMMENDED ✅

### Install WSL
```powershell
# In PowerShell as Administrator:
wsl --install
```

This installs Ubuntu by default. Restart your computer after installation.

### Access Your Project
```bash
# WSL can access your Windows files:
cd /mnt/c/Users/YourUsername/multi-agent-trading-system

# Or clone the project directly in WSL:
cd ~
git clone [your-repo-url]
cd multi-agent-trading-system
```

### Run the System
```bash
# Everything works exactly the same:
./service_manager.sh start all
./service_manager.sh stop all
./service_manager.sh status
```

### Install Dependencies in WSL
```bash
# Python
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create venv and install packages
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Option 2: Git Bash (Quick Start)

Git Bash provides bash environment on Windows.

### Install Git Bash
Download from: https://git-scm.com/downloads

### Run Services
```bash
# Open Git Bash in project directory
./service_manager.sh start all
```

**Note**: Git Bash has limited compatibility. Some features may not work.

---

## Option 3: Native Windows Script (service_manager.bat)

See `service_manager.bat` for Windows batch script equivalent.

### Usage
```cmd
REM In Command Prompt or PowerShell:
service_manager.bat start all
service_manager.bat stop all
service_manager.bat status
```

---

## Option 4: Manual Service Start (PowerShell)

```powershell
# Create logs directory if it doesn't exist
New-Item -ItemType Directory -Force -Path logs

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Start DataHub
Start-Process python -ArgumentList "start_datahub_server.py" -RedirectStandardOutput "logs\datahub.log" -RedirectStandardError "logs\datahub_error.log" -WindowStyle Hidden

# Wait for DataHub to start
Start-Sleep -Seconds 3

# Start WebSocket Collector
Start-Process python -ArgumentList "-u","websocket_collector_modern.py" -RedirectStandardOutput "logs\websocket.log" -RedirectStandardError "logs\websocket_error.log" -WindowStyle Hidden

# Wait for WebSocket to start
Start-Sleep -Seconds 3

# Start DataBento Client
Start-Process python -ArgumentList "-u","start_databento_client.py" -RedirectStandardOutput "logs\databento.log" -RedirectStandardError "logs\databento_error.log" -WindowStyle Hidden

# Wait for DataBento to start
Start-Sleep -Seconds 3

# Start Scalper
Start-Process python -ArgumentList "scalping_cli.py","--run" -RedirectStandardOutput "logs\scalping_engine.log" -RedirectStandardError "logs\scalping_error.log" -WindowStyle Hidden

# Wait for Scalper to start
Start-Sleep -Seconds 3

# Start Dashboard (opens in browser)
Start-Process streamlit -ArgumentList "run","dashboard_v2.py","--server.port","8505" -RedirectStandardOutput "logs\dashboard.log" -RedirectStandardError "logs\dashboard_error.log"

Write-Host "All services started!"
Write-Host "Dashboard: http://localhost:8505"
```

---

## Recommended Setup: WSL

**Why WSL?**
- ✅ 100% compatibility with existing scripts
- ✅ Native Linux environment
- ✅ Access to Windows files via `/mnt/c/`
- ✅ Can run PostgreSQL natively
- ✅ Better performance than Git Bash
- ✅ No code changes needed

**Setup Time**: 10-15 minutes
**Compatibility**: Perfect

---

## Database Setup on Windows

### Option A: PostgreSQL on Windows
Download from: https://www.postgresql.org/download/windows/

**After Installation**:
```cmd
REM Add PostgreSQL to PATH (usually in C:\Program Files\PostgreSQL\15\bin)

REM Create database
psql -U postgres -c "CREATE DATABASE forex_scalping;"
psql -U postgres -d forex_scalping -f database_setup.sql
```

### Option B: PostgreSQL in WSL
```bash
# In WSL:
sudo apt install postgresql postgresql-contrib
sudo service postgresql start

# Create database
sudo -u postgres psql -c "CREATE DATABASE forex_scalping;"
sudo -u postgres psql -d forex_scalping -f database_setup.sql
```

---

## Environment Variables on Windows

### PowerShell (Session Only)
```powershell
$env:DATABASE_URL="postgresql://username:password@localhost:5432/forex_scalping"
$env:IG_USERNAME="your_username"
$env:IG_PASSWORD="your_password"
$env:IG_API_KEY="your_api_key"
```

### Command Prompt (Session Only)
```cmd
set DATABASE_URL=postgresql://username:password@localhost:5432/forex_scalping
set IG_USERNAME=your_username
set IG_PASSWORD=your_password
set IG_API_KEY=your_api_key
```

### Permanent (System Environment Variables)
1. Press `Win + X` → System
2. Advanced system settings → Environment Variables
3. Under "System variables" click "New"
4. Add each variable:
   - Variable name: `DATABASE_URL`
   - Variable value: `postgresql://username:password@localhost:5432/forex_scalping`
5. Click OK

**OR** use PowerShell (requires Admin):
```powershell
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql://username:password@localhost:5432/forex_scalping', [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable('IG_USERNAME', 'your_username', [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable('IG_PASSWORD', 'your_password', [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable('IG_API_KEY', 'your_api_key', [System.EnvironmentVariableTarget]::User)
```

---

## Quick Start (WSL Method) - Copy & Paste

```bash
# 1. Install WSL (in PowerShell as Administrator)
wsl --install

# 2. Restart computer

# 3. Open Ubuntu from Start Menu

# 4. Update Ubuntu
sudo apt update && sudo apt upgrade -y

# 5. Install dependencies
sudo apt install python3.11 python3.11-venv python3-pip postgresql git -y

# 6. Navigate to project (adjust path to your Windows username)
cd /mnt/c/Users/YourUsername/Desktop/multi-agent-trading-system

# 7. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 8. Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# 9. Start PostgreSQL
sudo service postgresql start

# 10. Create database
sudo -u postgres psql -c "CREATE DATABASE forex_scalping;"
sudo -u postgres psql -d forex_scalping -f database_setup.sql

# 11. Configure environment (edit .env file)
cp .env.example .env
nano .env  # Add your IG credentials

# 12. Start all services
chmod +x service_manager.sh
./service_manager.sh start all

# 13. Check status
./service_manager.sh status

# 14. View logs
tail -f logs/scalping_engine.log
```

Done! 🚀

---

## Troubleshooting Windows

### WSL Not Found
```powershell
# Enable WSL feature (PowerShell as Administrator)
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart computer
# Then install Ubuntu from Microsoft Store
```

### Port Already in Use
```powershell
# Find process using port 8505
netstat -ano | findstr :8505

# Kill process (replace 1234 with actual PID)
taskkill /PID 1234 /F
```

### PostgreSQL Connection Issues
```powershell
# Check if PostgreSQL service is running
# Press Win+R, type: services.msc
# Look for "postgresql-x64-15" service
# Right-click → Start
```

### Permission Denied on .sh files
```bash
# In WSL or Git Bash:
chmod +x service_manager.sh
dos2unix service_manager.sh  # If line endings are wrong
```

### Python Not Found
```bash
# In WSL:
sudo apt install python3.11 python3.11-venv python3-pip

# On Windows:
# Download from https://www.python.org/downloads/
# Make sure "Add Python to PATH" is checked during installation
```

---

## Performance Tips

1. **Use WSL 2** (better performance):
   ```powershell
   wsl --set-default-version 2
   ```

2. **Store project files in WSL** (faster I/O):
   ```bash
   # Clone in WSL home directory instead of /mnt/c/
   cd ~
   git clone [your-repo]
   cd multi-agent-trading-system
   ```

3. **Allocate more RAM to WSL** (optional):
   Create `C:\Users\YourUsername\.wslconfig`:
   ```ini
   [wsl2]
   memory=4GB
   processors=2
   ```

---

## Next Steps After Setup

1. **Verify data collection**:
   ```bash
   # Check if ticks are being saved
   sudo -u postgres psql -d forex_scalping -c "SELECT COUNT(*) FROM ig_spot_ticks;"
   ```

2. **Monitor logs**:
   ```bash
   # Watch scalper progress
   tail -f logs/scalping_engine.log | grep "candles"
   ```

3. **Access dashboard**:
   - Open browser: http://localhost:8505
   - View real-time spreads, candles, and trade analysis

4. **Wait for sufficient data**:
   - System needs 30 candles (~30 minutes)
   - Watch logs for countdown: "need X more candles"

---

## Support

- **WSL Documentation**: https://learn.microsoft.com/en-us/windows/wsl/
- **PostgreSQL Windows**: https://www.postgresql.org/download/windows/
- **Git Bash**: https://git-scm.com/downloads
