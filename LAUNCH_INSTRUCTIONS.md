# How to Launch IG Real Trading Dashboard

## 🪟 Windows

Double-click:
```
start_ig_dashboard.bat
```

Or open Command Prompt and run:
```cmd
start_ig_dashboard.bat
```

## 🐧 Linux / 🍎 macOS

Open Terminal and run:
```bash
./start_ig_dashboard.sh
```

Or:
```bash
bash start_ig_dashboard.sh
```

## 📱 Any Platform (Direct Command)

```bash
streamlit run ig_trading_dashboard.py
```

---

## 🌐 Dashboard URL

Once launched, open your browser and go to:

**http://localhost:8501**

The dashboard will automatically open in your default browser.

---

## ⚠️ First Time Setup

If you get "permission denied" on Linux/Mac:

```bash
chmod +x start_ig_dashboard.sh
```

Then run:
```bash
./start_ig_dashboard.sh
```

---

## 🚀 Quick Start

1. **Launch dashboard** (use method above for your OS)
2. **Click "▶️ Start"** in the sidebar
3. **Watch signals** appear in real-time
4. **Enable auto-trading** when ready (checkbox in sidebar)
5. **Click "⏹️ Stop"** when done

---

## 📊 What Happens When You Start

✅ Background worker launches automatically
✅ Scans 5 forex pairs every 60 seconds
✅ Generates AI trading signals
✅ Shows real-time data from IG account
✅ Executes REAL trades (when auto-trading enabled)

---

## 🛡️ Safety

- Auto-trading is **OFF by default**
- Test with signals only first
- Enable auto-trading when confident
- Click Stop button anytime to halt trading

---

## 📝 Full Documentation

See `DASHBOARD_READY.md` for complete guide.

**Happy Trading!** 🚀
