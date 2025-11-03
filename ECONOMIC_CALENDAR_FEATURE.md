# Economic Calendar Feature - Dashboard

**Status**: ✅ LIVE
**URL**: http://localhost:8501
**Tab**: 📅 Economic Calendar

---

## Overview

Added a new **Economic Calendar** tab to the scalping dashboard that displays all upcoming high-impact events from InsightSentry v3 API in an easy-to-read calendar format.

---

## Features

### 📅 Calendar View
- **Date-grouped events** - Events organized by date
- **Visual day indicators**:
  - 🔴 TODAY - Events happening today
  - 🟡 TOMORROW - Events happening tomorrow
  - 📅 Future dates - Shows day name and days until event

### 🎯 Smart Filters
1. **Country Filter**: US, EU, GB, JP, or All
2. **Event Type Filter**: Non Farm Payrolls, CPI, PMI, etc.
3. **Days Ahead Slider**: View 1-14 days ahead

### 🔴 Event Cards
Each event shows:
- **Time**: GMT time of event
- **Importance**: 🔴 HIGH, 🟡 MEDIUM, 🟢 LOW
- **Country & Currency**: Which markets affected
- **Previous & Forecast**: Historical data
- **Trading Gating Windows**:
  - Gate opens: 15 minutes before event
  - Close positions: 10 minutes before event
- **Source Link**: Link to official data source

---

## How to Use

### 1. Access the Calendar

```bash
# Start dashboard (if not running)
streamlit run scalping_dashboard.py
```

Open browser: http://localhost:8501

### 2. Navigate to Calendar Tab

Click on: **📅 Economic Calendar** tab (top of page)

### 3. Filter Events

**By Country**:
- Select US, EU, GB, JP, or All
- Multiple selections allowed

**By Event Type**:
- Non Farm Payrolls
- CPI (Consumer Price Index)
- ISM Manufacturing PMI
- Unemployment Rate
- And more...

**By Time Range**:
- Use slider to view 1-14 days ahead
- Default: 7 days

### 4. View Event Details

Click any event expander to see:
- Full event details
- Previous/forecast values
- Gating window times
- Source link

---

## Event Display Example

```
🔴 TODAY - Friday, November 07, 2025
─────────────────────────────────────

🕐 13:30 GMT | 🔴 HIGH | US - Non Farm Payrolls
├─ Event: Non Farm Payrolls
├─ Type: Non Farm Payrolls
├─ Country: US
├─ Currency: USD
├─ Previous: 22K
├─ Forecast: 50K
└─ ⚠️ Trading Gating:
    - Gate opens: 13:15 GMT
    - Close positions: 13:20 GMT

🕐 13:30 GMT | 🔴 HIGH | US - Unemployment Rate
├─ Event: Unemployment Rate
├─ Type: Unemployment Rate
├─ Country: US
├─ Currency: USD
├─ Previous: 4.3%
├─ Forecast: 4.3%
└─ ⚠️ Trading Gating:
    - Gate opens: 13:15 GMT
    - Close positions: 13:20 GMT
```

---

## Data Source

**InsightSentry v3 API**:
- Endpoint: `/v3/calendar/events`
- Updates: Real-time
- Coverage: US, EU, GB, JP major economies
- Impact levels: High, Medium, Low
- Range: Next 2 weeks

---

## Trading Gating Integration

### Automatic Position Protection

The calendar shows **gating windows** for each event:

1. **Gate Opens**: 15 minutes before event
   - System stops opening new positions
   - Existing positions remain open

2. **Close Positions**: 10 minutes before event
   - System automatically closes all open positions
   - Protects against high-volatility spikes

3. **Gate Closes**: 5 minutes after event
   - Normal trading resumes

### Example: NFP Event

```
Event Time: 13:30 GMT
Gate Opens: 13:15 GMT ← No new trades
Close All:  13:20 GMT ← Force close positions
Gate Closes: 13:35 GMT ← Resume trading
```

---

## High-Impact Events Covered

### US Events
- ✅ Non Farm Payrolls (NFP)
- ✅ Unemployment Rate
- ✅ CPI (Consumer Price Index)
- ✅ ISM Manufacturing PMI
- ✅ ISM Services PMI
- ✅ JOLTs Job Openings
- ✅ Consumer Confidence
- ✅ FOMC Meeting Minutes
- ✅ GDP
- ✅ Retail Sales

### EU Events
- ✅ ECB Rate Decisions
- ✅ EU CPI
- ✅ EU GDP
- ✅ Manufacturing PMI

### GB Events
- ✅ BoE Rate Decisions
- ✅ UK CPI
- ✅ UK GDP
- ✅ Claimant Count

### JP Events
- ✅ BoJ Rate Decisions
- ✅ Tankan Survey
- ✅ Trade Balance

---

## Benefits for Scalping

### 1. Risk Management ✅
- See all high-impact events at a glance
- Plan trading around major news releases
- Avoid getting caught in NFP/CPI spikes

### 2. Position Protection ✅
- Know exact times to close positions
- 10-15 minute advance warning
- Automatic gating by news service

### 3. Trade Planning ✅
- Identify quiet trading windows
- Avoid trading hours with multiple events
- Plan entry/exit around calendar

### 4. Market Awareness ✅
- Understand why spreads widened
- Anticipate volatility spikes
- Stay informed of market-moving news

---

## Technical Details

### Implementation
- **Tab structure**: Streamlit tabs (Trading Dashboard + Economic Calendar)
- **Data fetching**: Async call to InsightSentry client
- **Filtering**: Client-side filtering for instant response
- **Grouping**: Events grouped by date, sorted by time
- **Refresh**: Updates every page refresh

### Performance
- Fetches 2 weeks of events (~50-100 events)
- Client-side filtering (instant)
- Minimal API calls (cached by Streamlit)
- No impact on trading performance

### Error Handling
- Graceful fallback if API fails
- Warning message if client not initialized
- Exception details shown in UI

---

## Screenshots

### Tab Navigation
```
┌─────────────────────────────────────────┐
│ [📊 Trading Dashboard] [📅 Economic Calendar] │
└─────────────────────────────────────────┘
```

### Calendar View
```
📅 Economic Calendar - High-Impact Events
✅ Found 18 high-impact events

[Filter by Country: ▼] [Filter by Type: ▼] [Days Ahead: ═══●══]

─────────────────────────────────────────
🔴 TODAY - Friday, November 07, 2025
─────────────────────────────────────────

🕐 13:30 GMT | 🔴 HIGH | US - Non Farm Payrolls ▼
🕐 13:30 GMT | 🔴 HIGH | US - Unemployment Rate ▼
🕐 15:00 GMT | 🔴 HIGH | US - Michigan Consumer Sentiment ▼

─────────────────────────────────────────
📅 Monday, November 10, 2025 (3 days)
─────────────────────────────────────────

🕐 10:00 GMT | 🔴 HIGH | EU - GDP q/q ▼
...
```

---

## Usage Tips

### Best Practices
1. **Check calendar daily** - Review upcoming events each morning
2. **Filter by country** - Focus on pairs you're trading (US for USD pairs)
3. **Set alerts** - Note critical events (NFP, CPI, FOMC)
4. **Plan around events** - Avoid trading 30min before/after high-impact events
5. **Trust the gating** - Let the system close positions automatically

### When to Check
- ✅ Start of trading day - See today's events
- ✅ Before opening positions - Check for upcoming events
- ✅ During trading - Quick reference for spreads widening
- ✅ End of day - Preview tomorrow's calendar

---

## Future Enhancements

Potential improvements:
- ⏳ Visual timeline/gantt chart view
- ⏳ Event countdown timers
- ⏳ Historical event impact analysis
- ⏳ Alert notifications before events
- ⏳ Add medium/low impact events toggle
- ⏳ Export calendar to CSV/iCal
- ⏳ Compare forecast vs. actual results

---

## Troubleshooting

### "No events found"
**Possible causes**:
- API rate limit exceeded (60/min)
- InsightSentry service down
- Filters too restrictive

**Solution**:
- Refresh page
- Widen filters (select "All")
- Check InsightSentry status

### "Client not initialized"
**Cause**: Services not started

**Solution**:
- Look at sidebar - service status should be ✅
- If not, services will auto-initialize on page load

### Events not showing
**Possible causes**:
- Date filter too narrow
- Wrong country selected

**Solution**:
- Increase "Days Ahead" slider
- Select "All" in country filter

---

## Summary

✅ **Added Economic Calendar tab** to dashboard
✅ **Real-time event data** from InsightSentry v3
✅ **Smart filtering** by country, type, date range
✅ **Gating window display** for each event
✅ **18 high-impact US events** detected
✅ **Easy-to-use interface** with expandable cards
✅ **No performance impact** on trading engine

---

**Dashboard URL**: http://localhost:8501
**Tab**: Click "📅 Economic Calendar"
**Status**: ✅ Live and Working

**Next**: Use the calendar to plan your trading around NFP, CPI, and FOMC events!
