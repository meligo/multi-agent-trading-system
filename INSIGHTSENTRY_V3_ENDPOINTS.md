# InsightSentry v3 API Endpoints Documentation

**Base URL**: `https://insightsentry.p.rapidapi.com`
**API Key**: Set in `INSIGHTSENTRY_RAPIDAPI_KEY` environment variable
**Plan**: MEGA ($50/month)

---

## ✅ Working Endpoints

### 1. Calendar Events (Economic Calendar)

**Endpoint**: `/v3/calendar/events`

**Purpose**: Get economic calendar events including NFP, PMI, CPI, FOMC, etc.

**Parameters**:
- `w` - Weeks ahead (1-4)
- `country` - Country code (US, EU, GB, JP, etc.)
- `currency` - Currency code (USD, EUR, GBP, JPY)
- `importance` - Event importance (low, medium, high)

**Example Requests**:
```bash
# Get all events for next week
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/calendar/events?w=1' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'

# Get high-impact US events
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/calendar/events?country=US&importance=high&w=1' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'

# Get USD currency events
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/calendar/events?currency=USD&w=2' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'
```

**Response Structure**:
```json
{
  "total_count": 607,
  "range": "From 2025-11-01 to 2025-11-08",
  "last_update": 1762108547091,
  "data": [
    {
      "title": "Non Farm Payrolls",
      "country": "US",
      "type": "Non Farm Payrolls",
      "reference_date": "2025-10-31T00:00:00Z",
      "source_url": "http://www.bls.gov/",
      "previous": 22,
      "forecast": 50,
      "currency": "USD",
      "importance": "high",
      "date": "2025-11-07T13:30:00.000Z"
    }
  ]
}
```

**Event Types Included**:
- Non Farm Payrolls (NFP)
- Unemployment Rate
- CPI (Consumer Price Index)
- ISM Manufacturing PMI
- ISM Services PMI
- JOLTs Job Openings
- Consumer Confidence
- GDP
- FOMC Meeting
- Central Bank Decisions
- Retail Sales
- And many more...

---

### 2. Calendar Earnings

**Endpoint**: `/v3/calendar/earnings`

**Purpose**: Get earnings reports for stocks

**Parameters**:
- `w` - Weeks ahead (1-4)

**Example**:
```bash
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/calendar/earnings?w=1' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'
```

**Response Structure**:
```json
{
  "total_count": 4299,
  "range": "From 2025-11-01 to 2025-11-08",
  "last_update": 1762108555321,
  "data": [
    {
      "code": "NYSE:BRK.A",
      "earnings_release_next_date": 1762171200,
      "earnings_release_date": 1754136000,
      "name": "Berkshire Hathaway Inc.",
      "earnings_per_share_fq": 7749.809595,
      "revenue_fq": 92515000000,
      "market_cap": 1029904359960,
      "currency_code": "USD"
    }
  ]
}
```

---

### 3. Calendar Dividends

**Endpoint**: `/v3/calendar/dividends`

**Purpose**: Get dividend payment schedules

**Parameters**:
- `w` - Weeks ahead (1-4)

**Example**:
```bash
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/calendar/dividends?w=1' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'
```

**Response Structure**:
```json
{
  "total_count": 2723,
  "range": "From 2025-11-01 to 2025-11-08",
  "last_update": 1762108563751,
  "data": [
    {
      "code": "BX:TRVC",
      "dividend_ex_date_recent": 1754308740,
      "dividend_ex_date_upcoming": 1762171140,
      "name": "Citigroup Inc.",
      "dividends_yield": 2.3708386,
      "dividend_amount_recent": 0.600000024,
      "currency_code": "USD"
    }
  ]
}
```

---

### 4. News Feed

**Endpoint**: `/v3/newsfeed`

**Purpose**: Get breaking financial news

**Parameters**:
- `page` - Page number (starts at 1)

**Example**:
```bash
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/newsfeed?page=1' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'
```

**Response Structure**:
```json
{
  "last_update": 1762106939,
  "total_items": 69235,
  "current_items": 500,
  "page": 1,
  "has_next": true,
  "data": [
    {
      "source": "Reuters",
      "title": "Bessent says high US interest rates may have caused housing recession",
      "content": "Full article text...",
      "published_at": 1762106652,
      "link": "https://...",
      "related_symbols": ["NYSE:LUV", "NYSE:BA"]
    }
  ]
}
```

---

### 5. Symbol Search

**Endpoint**: `/v3/symbols/search`

**Purpose**: Search for symbols/tickers

**Parameters**:
- `query` - Search query (e.g., "EURUSD", "Apple")
- `symbol` - Direct symbol lookup

**Example**:
```bash
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v3/symbols/search?query=EURUSD' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: YOUR_KEY'
```

**Response Structure**:
```json
{
  "current_page": 1,
  "has_more": false,
  "data": [...]
}
```

---

## ❌ Non-Existent Endpoints

The following endpoints do NOT exist in v3:

- `/v3/calendar` (without sub-path)
- `/v3/calendar/economic`
- `/v3/calendar/ipos`
- `/v3/calendar/splits`
- `/v3/news` (use `/v3/newsfeed` instead)
- `/v3/sentiment`
- `/v3/quote`
- `/v3/quotes`
- `/v3/forex`
- `/v3/economic`
- `/v3/websocket-key` (likely requires different auth)

---

## Key Differences from v2

| Feature | v2 (Old - Broken) | v3 (New - Working) |
|---------|-------------------|-------------------|
| Economic Calendar | `/v2/calendar/economic` ❌ | `/v3/calendar/events` ✅ |
| News | `/v2/news` ❌ | `/v3/newsfeed` ✅ |
| Sentiment | `/v2/sentiment` ❌ | Not available |
| Symbol Info | `/v2/symbols/{symbol}/info` ❌ | `/v3/symbols/search` ✅ |

---

## Usage in Scalping System

### For News Gating Service

Use `/v3/calendar/events` with these filters:
```python
params = {
    "country": "US,EU,GB,JP",  # Forex majors
    "importance": "high",       # Only high-impact
    "w": 1                      # Next week
}
```

Filter client-side for forex-relevant events:
- NFP (Non Farm Payrolls)
- CPI (Consumer Price Index)
- FOMC Meetings
- Central Bank Rate Decisions
- GDP Releases
- Unemployment Rate

### For Breaking News Monitoring

Use `/v3/newsfeed`:
```python
params = {
    "page": 1  # First page, 500 items
}
```

Filter by `related_symbols` for FX pairs or by content keywords.

---

## Rate Limits

**MEGA Plan**:
- 600,000 requests/month (REST API)
- ~20,000 requests/day
- 60 requests/minute rate limit
- 10 WebSocket connections/day (hard limit - use carefully!)

**Recommendations**:
- Poll `/v3/calendar/events` every 60 seconds
- Poll `/v3/newsfeed` every 30-60 seconds for breaking news
- Cache responses aggressively
- Filter server-side where possible (use query parameters)

---

## Implementation Priority

1. **High Priority**: `/v3/calendar/events` - Critical for news gating
2. **Medium Priority**: `/v3/newsfeed` - Breaking news detection
3. **Low Priority**: `/v3/calendar/earnings`, `/v3/calendar/dividends` - Equity-focused

---

## Next Steps

1. ✅ Update `insightsentry_client.py` to use v3 endpoints
2. ✅ Add filtering for high-impact forex events
3. ✅ Update news gating service to parse v3 response format
4. ✅ Test with live data
5. ✅ Monitor rate limits

---

**Status**: Fully documented and ready for implementation
**Date**: November 2, 2025
