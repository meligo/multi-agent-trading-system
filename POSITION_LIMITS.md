# Position Limit Management

## Overview

The system now includes **position limit management** to prevent overtrading and manage risk effectively, especially important when restarting the dashboard.

## Configuration

Edit `forex_config.py`:

```python
# Risk Management
MAX_OPEN_POSITIONS: int = 20  # Maximum concurrent open positions
CHECK_IG_POSITIONS_ON_STARTUP: bool = True  # Check IG for existing positions on startup
```

## How It Works

### 1. Startup Position Check

When the worker initializes, it:
1. **Connects to IG** and fetches all open positions
2. **Counts existing positions** from previous sessions/restarts
3. **Calculates available slots** (MAX - current)
4. **Displays the status** prominently

**Example Output:**
```
================================================================================
IG REAL TRADING WORKER INITIALIZED
================================================================================
Account: Z64WQT - CFD
Balance: €20,000.00
Available: €16,587.51

⚠️  EXISTING OPEN POSITIONS: 5
   These positions were found on IG (from previous session)

Settings:
   Auto-trading: 🔴 ENABLED (LIVE TRADES!)
   Max open positions: 20
   Current positions: 5
   Available slots: 15    ← Can only open 15 more trades!
   Max workers: 1
   Update interval: 60s
   Monitoring pairs: 28
================================================================================
```

### 2. Pre-Trade Position Check

Before executing each new trade, the system:
1. **Fetches current open positions** from IG in real-time
2. **Checks against MAX_OPEN_POSITIONS limit**
3. **Skips the trade** if limit is reached
4. **Shows available slots** for transparency

**Example Output:**
```bash
🔍 Analyzing EUR_USD...
   ✅ BUY signal (confidence: 0.75)

📊 Position check: 18/20 open (2 slots available)
✅ REAL TRADE EXECUTED: EUR_USD BUY 0.1 lots
   Deal reference: ABC123DEF456

🔍 Analyzing GBP_USD...
   ✅ SELL signal (confidence: 0.80)

📊 Position check: 19/20 open (1 slot available)
✅ REAL TRADE EXECUTED: GBP_USD SELL 0.1 lots
   Deal reference: XYZ789GHI012

🔍 Analyzing USD_JPY...
   ✅ BUY signal (confidence: 0.85)

⚠️  Position limit reached: 20/20
   Skipping USD_JPY BUY signal
```

## Why This Matters

### Without Position Limits
```
Scenario: Dashboard crashes and restarts
- IG has 5 open positions from before crash
- System doesn't know about them
- System opens 20 MORE positions
- Total: 25 positions (OVERTRADED!)
- Risk exposure: TOO HIGH
```

### With Position Limits ✅
```
Scenario: Dashboard crashes and restarts
- IG has 5 open positions from before crash
- System checks IG on startup: "5 positions found"
- System calculates: 20 max - 5 existing = 15 available
- System opens maximum 15 new positions
- Total: 20 positions (CONTROLLED!)
- Risk exposure: MANAGED
```

## Risk Management Benefits

### 1. Prevents Overexposure
- **Limits total concurrent trades** to a safe number
- **Controls maximum risk** (e.g., 20 trades × 1% = 20% total at risk)
- **Prevents account blow-up** from too many simultaneous positions

### 2. Handles Restarts Gracefully
- **Remembers existing positions** even after system restarts
- **Continues trading** without exceeding limits
- **No duplicate positions** on the same signal

### 3. Provides Transparency
- **Shows position counts** at startup
- **Displays available slots** before each trade
- **Warns when limit reached** clearly

## Configuration Examples

### Conservative (Small Account)
```python
MAX_OPEN_POSITIONS: int = 5  # Very conservative
```
- 5 positions × 1% risk = 5% total risk
- Good for: €1,000 - €5,000 accounts
- Less opportunities but safer

### Moderate (Medium Account)
```python
MAX_OPEN_POSITIONS: int = 10  # Moderate risk
```
- 10 positions × 1% risk = 10% total risk
- Good for: €5,000 - €20,000 accounts
- Balance between opportunity and safety

### Aggressive (Large Account)
```python
MAX_OPEN_POSITIONS: int = 20  # Default
```
- 20 positions × 1% risk = 20% total risk
- Good for: €20,000+ accounts
- More opportunities, higher risk

### Very Aggressive (Professional)
```python
MAX_OPEN_POSITIONS: int = 50  # High risk!
```
- 50 positions × 1% risk = 50% total risk
- Good for: Experienced traders only
- Maximum opportunities, maximum risk

## Interaction with Other Risk Controls

The system has **multiple layers of risk management**:

### Layer 1: Position Size
- 1% risk per trade (RISK_PERCENT)
- Max position size: 10.0 lots MINI (MAX_POSITION_SIZE)

### Layer 2: Stop Loss/Take Profit
- Every trade has SL and TP
- Risk/reward ratio calculated
- Minimum 1.5:1 R:R required

### Layer 3: Position Count (NEW!)
- Maximum concurrent positions (MAX_OPEN_POSITIONS)
- Pre-trade position check
- Startup position discovery

### Layer 4: Account Balance
- Available funds checked before trading
- Margin requirements respected
- No trades if insufficient funds

### Combined Example:
```
Account: €20,000
RISK_PERCENT: 1% = €200 per trade
MAX_OPEN_POSITIONS: 20

Maximum Risk Scenario:
- 20 trades open simultaneously
- Each risking €200 (at SL)
- Total at risk: €4,000 (20% of account)
- Still 80% of capital safe!
```

## Dashboard Display

The dashboard will show:
- **Overview Tab**: Current/Max positions
- **Positions Tab**: All open positions with details
- **Terminal Output**: Real-time position counts

**Example:**
```
Account Overview
├── Balance: €20,000
├── Available: €15,000 (margin used)
├── Open Positions: 12/20  ← Position limit visible
└── Auto-Trading: ENABLED
```

## Restart Scenarios

### Scenario 1: Clean Start
```
1. Start dashboard
2. No existing positions on IG
3. System shows: 0/20 open (20 slots available)
4. System can open up to 20 trades
```

### Scenario 2: Restart After Crash
```
1. System was running with 8 open trades
2. Dashboard crashed/stopped
3. Restart dashboard
4. System checks IG: 8 positions found
5. System shows: 8/20 open (12 slots available)
6. System can open 12 more trades
```

### Scenario 3: Limit Reached
```
1. System opens 20 trades over time
2. All signals continue to generate
3. Position check: 20/20 (limit reached)
4. New signals are skipped with warning
5. Existing positions monitored
6. When position closes: 19/20 (1 slot free)
7. Next signal can open new trade
```

## Disabling Position Limits

If you want **unlimited positions** (not recommended!):

```python
# forex_config.py
MAX_OPEN_POSITIONS: int = 999  # Effectively unlimited
CHECK_IG_POSITIONS_ON_STARTUP: bool = False  # Don't check on startup
```

**⚠️ Warning**: Only disable for:
- Testing/development
- Very large accounts (€100k+)
- Experienced traders who understand the risks

## Monitoring Position Limits

### In Dashboard
- Overview tab shows current/max positions
- Positions tab lists all open trades
- Updates automatically every cycle

### In Terminal
- Startup: Shows existing positions
- Each signal: Shows position check
- Limit reached: Clear warning message

### In IG Platform
- Log into IG directly
- View all open positions
- See margin usage and P&L
- Close positions manually if needed

## Best Practices

### 1. Set Appropriate Limits
- **Small accounts (< €5k)**: MAX_OPEN_POSITIONS = 5
- **Medium accounts (€5k-€20k)**: MAX_OPEN_POSITIONS = 10
- **Large accounts (€20k+)**: MAX_OPEN_POSITIONS = 20

### 2. Monitor Regularly
- Check position count in dashboard
- Review open positions daily
- Close losing positions if needed
- Adjust limits based on performance

### 3. Respect the Limits
- Don't override position limits
- Don't open positions manually on IG while system running
- If you do, system will include them in count (good!)

### 4. Restart Safely
- System handles restarts automatically
- Existing positions are counted
- No action needed from you
- Just restart and it works!

## Testing the Feature

### Test 1: Startup with Existing Positions
```bash
# 1. Manually open 5 positions on IG
# 2. Start dashboard
# 3. Check terminal output
# Expected: "EXISTING OPEN POSITIONS: 5"
# Expected: "Available slots: 15"
```

### Test 2: Reaching the Limit
```bash
# 1. Set MAX_OPEN_POSITIONS = 3 (for testing)
# 2. Start dashboard with auto-trading
# 3. Wait for 3 trades to execute
# 4. Watch next signal
# Expected: "Position limit reached: 3/3"
# Expected: "Skipping [pair] [signal] signal"
```

### Test 3: Position Released
```bash
# 1. Have 3/3 positions open (limit reached)
# 2. Manually close 1 position on IG
# 3. Wait for next signal
# Expected: "Position check: 2/3 open (1 slot available)"
# Expected: Trade executes successfully
```

## FAQ

**Q: What if IG API fails to return position count?**
A: System logs a warning and proceeds with trade (safer to execute than skip)

**Q: Can I change MAX_OPEN_POSITIONS while running?**
A: Yes, edit forex_config.py and restart dashboard

**Q: Do closed positions count toward the limit?**
A: No, only OPEN positions count

**Q: What if I manually close a position on IG?**
A: System will detect it on next position check (before next trade)

**Q: Does this work with both MINI and standard markets?**
A: Yes, works with any IG market type

**Q: Can different pairs have different limits?**
A: Not yet, but could be added as a future feature

## Summary

**Position limit management**:
✅ Prevents overtrading
✅ Handles restarts gracefully
✅ Provides clear visibility
✅ Multiple risk layers
✅ Easy to configure
✅ Works automatically

**Your trading is now safer and more controlled!** 🛡️
