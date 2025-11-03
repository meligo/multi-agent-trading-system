# 🚀 QUICK FIX GUIDE

**Problem**: No data being collected despite markets being open

**Root Cause**: IG API credentials invalid (username OR password wrong)

**Solution**: 3 steps, 5 minutes

---

## Step 1: Fix IG Credentials

### 1.1 Verify Your Username

Go to https://www.ig.com/ and try logging in manually.

**Is your username actually `meligokes`?**
- ✅ Yes → Move to password check
- ❌ No → Update `.env.scalper` with correct username

### 1.2 Verify Your Password

**Is your password `$Demo001`?**
- ✅ Yes, I'm sure → Contact IG support (account might be locked)
- ❌ Not sure → Try logging in manually at https://www.ig.com/
- ❌ Different → Update `.env.scalper` with correct password

### 1.3 Update .env.scalper

Edit `/Users/meligo/multi-agent-trading-system/.env.scalper`:

```bash
IG_API_KEY=79ae278ca555968dda0d4837b90b813c4c941fdc  # Keep this
IG_USERNAME=<your_actual_username>  # Change if wrong
IG_PASSWORD=<your_actual_password>  # Change if wrong
```

---

## Step 2: Test The Fix

```bash
python test_ig_both_keys.py
```

**Expected Output**:
```
✅ SUCCESS - This key WORKS!
   Accounts: 1
   - Demo Account (DEMO): £10,000.00
```

**If still fails**:
- Double-check username/password are EXACTLY correct
- Try resetting password on IG website
- Contact IG support if account is locked

---

## Step 3: Restart Dashboard

```bash
streamlit run scalping_dashboard.py
```

**Watch for these log lines** (should appear within 60 seconds):

```
✅ DataHub manager started at 127.0.0.1:50000
✅ WebSocket collector started
📊 EUR_USD: Tick received @ 1.0850/1.0851  ← THIS MEANS IT WORKS!
📊 1-minute candle aggregated: EUR_USD
✅ Finnhub consensus: BULLISH (18 buy, 5 sell)
📡 DataBento: Processed 1,234 messages
```

---

## Step 4: Verify Data Collection

```bash
python test_all_data_sources.py
```

**Expected Output**:
```
✅ Data Sources:
   IG Markets:  ✅ WORKING
   Finnhub:     ✅ WORKING
   DataBento:   ✅ WORKING

📊 Database:
   IG Data:     ✅ HAS DATA (12,345 ticks, 234 candles)

🎉 ALL CRITICAL SYSTEMS WORKING
```

---

## If Still Not Working

### Problem: Can't log in to IG website

**Solution**: Reset password
1. Go to https://www.ig.com/uk/password-reset
2. Enter your email
3. Follow reset instructions
4. Update `.env.scalper` with new password
5. Run `python test_ig_both_keys.py`

### Problem: Don't remember username

**Solution**: Check email
1. Search your email for "IG"
2. Look for registration/welcome emails
3. Username is usually in the email
4. Update `.env.scalper` with correct username
5. Run `python test_ig_both_keys.py`

### Problem: Account locked/suspended

**Solution**: Contact IG
1. Call IG support: +44 (0)20 7896 0011
2. Explain you can't access API
3. They'll unlock your account
4. Run `python test_ig_both_keys.py`

### Problem: API key expired

**Solution**: Generate new key
1. Log in to https://labs.ig.com/
2. Go to "API Keys"
3. Click "Generate New Key"
4. Copy the key
5. Update `.env.scalper`:
   ```
   IG_API_KEY=<new_key_here>
   ```
6. Run `python test_ig_both_keys.py`

---

## Current Status

### Working ✅
- ✅ Finnhub API (technical indicators)
- ✅ DataBento API (order flow)
- ✅ All database tables exist
- ✅ System architecture ready

### Blocked ❌
- ❌ IG Markets API (invalid username/password)

### Impact
- ❌ No OHLC candles
- ❌ Engine cannot analyze
- ❌ Cannot generate signals

---

## ETA to Full Operation

- **If you know correct username/password**: 2 minutes
- **If you need to reset password**: 10 minutes
- **If account is locked**: 1-2 hours (IG support response time)

---

## Quick Commands Reference

```bash
# Test IG credentials
python test_ig_both_keys.py

# Test all 3 data sources
python test_all_data_sources.py

# Check database has data
python check_websocket_status.py

# Restart dashboard
streamlit run scalping_dashboard.py
```

---

## What To Look For When It Works

### In Dashboard Logs
```
✅ WebSocket collector started
📊 Ticks flowing for EUR_USD, GBP_USD, USD_JPY
📊 Candles aggregating every 60 seconds
✅ Finnhub fetching indicators
📡 DataBento streaming order flow
```

### In Engine
```
✅ Fetched EUR_USD data: candles=True, spread=1.2
🚀 SIGNAL: BUY EUR_USD @ 1.0850
   Confidence: 72%
```

### In Database
```sql
SELECT COUNT(*) FROM ig_spot_ticks;    -- Should be > 0
SELECT COUNT(*) FROM ig_candles;       -- Should be > 0
SELECT COUNT(*) FROM cme_trades;       -- Should be > 0
```

---

**🎯 Bottom Line**: Fix IG credentials → Restart dashboard → Everything works!

**Need Help?** See `INVESTIGATION_COMPLETE.md` for full details.
