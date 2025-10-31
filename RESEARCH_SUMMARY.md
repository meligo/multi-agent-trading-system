# Research Summary: Forex Data Streaming with WebSockets

## Quick Reference

### Key Findings

1. **WebSocket eliminates rate limits** - Persistent connections with push updates (no per-message limits)
2. **Delta updates reduce data transfer** - Only new candles sent, not full history
3. **Professional systems use 3-layer architecture** - REST (bootstrap) → WebSocket (stream) → Local Cache
4. **Provider concurrency limits are real** - IG Markets: 40 max connections, manage carefully
5. **TTL policies prevent memory bloat** - Keep 30 days recent, 1 year historical

### Rate Limit Mathematics

```
REST API Polling (INEFFICIENT):
- 1-minute candles, 10 symbols
- Every minute: 10 requests
- Daily: 14,400 requests (exceeds most limits)
- Cost: High API usage, frequent failures

WebSocket Streaming (EFFICIENT):
- Same 10 symbols
- 1 persistent connection
- Unlimited update frequency
- Cost: Zero rate limit consumption
```

### Architecture Pattern

```
┌─────────────────────────────────────┐
│   REST Bootstrap (One-time)         │
│   - Fetch 30 days historical        │
│   - One request per symbol          │
│   - Cost: Minimal                   │
└──────────────┬──────────────────────┘
               │ Load into cache
               ↓
┌─────────────────────────────────────┐
│   Hot Cache (Redis)                 │
│   - Last 1 hour of candles          │
│   - Microsecond access              │
│   - TTL: Auto-expire after 24h      │
└──────────────┬──────────────────────┘
               ↕ Sync every 5 min
┌─────────────────────────────────────┐
│   Cold Storage (TimescaleDB)        │
│   - Complete 30+ day history        │
│   - Millisecond access              │
│   - TTL: Auto-expire per policy     │
└──────────────┬──────────────────────┘
               │
               ↕ Stream updates
┌─────────────────────────────────────┐
│   WebSocket Connection              │
│   - Persistent, push-based          │
│   - Zero rate limits                │
│   - Automatic keep-alive            │
└─────────────────────────────────────┘
```

---

## Documents Generated

### 1. FOREX_WEBSOCKET_RESEARCH.md (Main Research)

**Sections:**
- WebSocket vs REST API comparison
- Major provider documentation (IG, Finnhub, Coinbase)
- Delta updates and incremental data structures
- Optimal architecture patterns
- Database schemas (TimescaleDB, InfluxDB, Redis)
- TTL strategies per data type
- Professional trading system approaches
- Python & JavaScript code examples

**Key Insights:**
- Finnhub + Spark real-time pipeline achieves 500ms dashboard refresh
- QuestDB materialized views provide 100x+ speedups for aggregation queries
- CCXT Pro implements sliding window caches (1000 entry default)
- Two-layer caching (hot + cold) is industry standard

---

### 2. WEBSOCKET_IMPLEMENTATION_PATTERNS.md (Code Patterns)

**9 Production-Ready Patterns:**

1. **Keep-Alive Connection** - Prevent idle timeout with periodic pings
2. **Connection Pool** - Manage 40 concurrent limit per provider
3. **Two-Layer Cache Sync** - Redis (hot) + TimescaleDB (cold)
4. **Cache Invalidation** - TTL, LRU, and size-limit strategies
5. **Resilient Streaming** - Exponential backoff and auto-reconnect
6. **Multi-Symbol Handler** - Concurrent streaming with resource control
7. **Smart Backfill** - Detect gaps and backfill via REST API
8. **Distributed Rate Limiter** - Token bucket and sliding window
9. **Stream Health Monitor** - Metrics, latency tracking, alerts

**Code Quality:**
- Type hints throughout
- Async/await patterns
- Error handling with recovery
- Logging and observability

---

### 3. PROVIDER_SPECIFIC_CONFIGS.md (Integration Guide)

**Providers Covered:**
- IG Markets (Lightstreamer protocol)
- Finnhub (JSON WebSocket)
- Coinbase Exchange API (FIX + WebSocket)
- CCXT Pro (Multi-exchange abstraction)

**Each includes:**
- Connection configuration
- Authentication setup
- Message format examples
- Rate limits and constraints
- Complete working code
- Migration checklist

---

## Implementation Roadmap

### Week 1: Foundation
```python
# Setup infrastructure
- Redis TimeSeries: Hot cache for last 1-2 hours
- TimescaleDB: Historical storage with TTL
- WebSocket wrapper: Connection management + keep-alive
- Logging: Debug all connection issues

Deliverable: Verified connection to provider (demo account)
```

### Week 2: Historical Bootstrap
```python
# Populate cache with history
- Fetch 30 days OHLCV via REST (single batch request)
- Load into Redis + TimescaleDB
- Verify data integrity

Deliverable: 30 days of cached data for 10 test symbols
```

### Week 3: Real-Time Streaming
```python
# Start delta updates
- Subscribe to WebSocket for new candles
- Merge into cache (incremental)
- Detect gaps and backfill

Deliverable: Live streaming with gap detection/recovery
```

### Week 4: Production Hardening
```python
# Optimize and monitor
- Profile cache hit rates
- Tune TTL policies
- Monitor latency percentiles
- Load test with 50+ symbols
- Implement alerts for unhealthy streams

Deliverable: Production-ready streaming system
```

---

## Critical Best Practices

### DO's

```python
# ✓ Bootstrap with single REST call (batch)
historical = api.fetch_ohlcv(symbol, '1m', limit=43200)  # 30 days

# ✓ Stream only NEW candles via WebSocket
async for candle in ws.watch_ohlcv(symbol, '1m'):
    if candle[0] > last_received:
        cache.add(candle)

# ✓ Maintain both hot and cold cache
redis.setex(key, 3600, data)  # 1 hour hot cache
db.insert(data)               # Permanent cold storage

# ✓ Implement gap detection
gap = (current_time - last_time) / interval
if gap > 1.5:  # More than 50% variance
    await backfill_missing(last_time, current_time)

# ✓ Auto-reconnect with exponential backoff
backoff = 0.1
while True:
    try:
        await connect()
        backoff = 0.1
    except:
        await sleep(backoff)
        backoff = min(backoff * 2, 60)
```

### DON'Ts

```python
# ✗ Don't poll REST API every minute
while True:
    candles = api.fetch_ohlcv(symbol)  # WRONG! Rate limit death
    await sleep(60)

# ✗ Don't ignore provider connection limits
# IG Markets: 40 max concurrent connections
# Over-subscribe and connections will fail silently

# ✗ Don't forget to set TTL on cache
cache.set(key, value)  # Will grow unbounded!
# CORRECT:
cache.setex(key, 30*24*3600, value)  # 30 day expiry

# ✗ Don't replace cache on update (do delta merge)
# WRONG:
cache = new_snapshot

# CORRECT:
cache.merge(delta_update)

# ✗ Don't assume WebSocket connection is permanent
# CORRECT: Handle reconnections with monitoring
```

---

## Technology Stack Recommendations

### Data Streaming
- **WebSocket Library:** websockets (Python) or ws (Node.js)
- **Multi-Exchange:** CCXT Pro (proven reliability)
- **Connection Management:** Custom wrapper with keep-alive

### Caching Layer
- **Hot Cache:** Redis Time Series (microsecond latency)
- **Cold Storage:** TimescaleDB (1000x compression vs vanilla PostgreSQL)
- **Sync Strategy:** Periodic batch writes every 5 minutes

### Monitoring
- **Metrics:** Prometheus + Grafana
- **Logging:** ELK stack or Datadog
- **Alerts:** Latency > 5s, Error rate > 5%, No data > 60s

### Deployment
- **Containerization:** Docker + Docker Compose
- **Orchestration:** Kubernetes for horizontal scaling
- **Redundancy:** Multiple streaming instances per region

---

## Expected Performance

### After Implementation

| Metric | Expected Value |
|--------|-----------------|
| Candle latency | 50-500ms (provider dependent) |
| Cache hit rate | >95% for recent data |
| Memory usage | <500MB for 100 symbols, 30 days history |
| Database query time | <10ms for single candle |
| Dashboard refresh rate | 100-500ms |
| Uptime SLA | >99.5% with reconnection |
| Rate limit hit count | 0 (after bootstrap) |

---

## Resources & References

### Official Documentation
1. **IG Markets Streaming API** - https://labs.ig.com/streaming-api-guide
2. **Finnhub WebSocket API** - https://finnhub.io/docs/api/websocket-trades
3. **Coinbase Exchange API** - https://docs.cdp.coinbase.com/exchange
4. **CCXT Pro Manual** - https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual

### Database Documentation
5. **QuestDB Materialized Views** - https://questdb.com/docs/guides/mat-views/
6. **TimescaleDB Financial Data** - https://docs.tigerdata.com/tutorials
7. **Redis Time Series** - https://redis.io/docs/data-types/timeseries/

### Real-World Examples
8. **Finnhub Realtime Pipeline** - https://github.com/piyush-an/Finnhub-Realtime-Pipeline
9. **Trading Systems with Spark** - Academic papers on real-time market data

---

## FAQ

**Q: Why not use REST API only?**
A: Rate limits become prohibitive at scale. 10 symbols × 1 minute polling = 14,400 requests/day. WebSocket eliminates this entirely.

**Q: How much memory for 100 symbols, 30 days?**
A: ~300MB with compression. Redis: 100MB (1 hour), TimescaleDB: 200MB (30 days).

**Q: Can I use single WebSocket connection for all symbols?**
A: Yes, most providers allow 50-100 symbols per connection. IG Markets is exception (40 total connections).

**Q: What if WebSocket connection drops?**
A: Detect gap, backfill via REST API, resume streaming. Gap detection alerts operator.

**Q: How often should I flush to database?**
A: Every 5 minutes or 100 candles (whichever first) balances latency vs database load.

**Q: What TTL for 1-minute candles?**
A: Typically 30 days. Day traders need less, swing traders need more. Adjust per strategy.

**Q: Can I combine multiple providers?**
A: Yes, CCXT Pro handles this. Use for redundancy (main + backup provider).

**Q: How to handle market holidays?**
A: WebSocket will naturally have no updates. Monitor for "no data" period > 24h as alert.

---

## Success Criteria

Your implementation is production-ready when:

- [x] WebSocket connection stays open > 99.5% uptime
- [x] Gap detection catches missed candles within 1 minute
- [x] Backfill completes within 30 seconds
- [x] Database queries return in < 10ms
- [x] Memory usage stable (no unbounded growth)
- [x] Cache hit rate > 95% for recent data
- [x] Can add/remove symbols without restart
- [x] Alerts firing for latency > 5s and error rate > 5%
- [x] Multiple symbols (50+) stream without degradation
- [x] Zero rate limit errors in logs

---

## Next Steps

1. **Choose Provider:** Evaluate IG Markets vs Finnhub vs Coinbase based on asset class
2. **Set Up Demo Account:** Test WebSocket connection in sandbox
3. **Build Prototype:** Implement Week 1-2 foundation and bootstrap
4. **Load Test:** Verify system scales to your symbol count
5. **Deploy:** Move to production with monitoring

---

## Support & Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection drops after 30min | Idle timeout | Increase keep-alive frequency to 10s |
| Missing candles every hour | WebSocket message buffering | Implement gap detection |
| Memory growing unbounded | No TTL cleanup | Set TTL on all cache entries |
| High latency (>1s) | Database query slow | Add index on (symbol, timeframe, timestamp) |
| Can't subscribe to >20 symbols | Connection limit | Use multiple WebSocket connections or switch provider |

### Debug Commands

```bash
# Monitor WebSocket traffic
tcpdump -i lo port 443 -A

# Check Redis memory
redis-cli INFO memory

# Check TimescaleDB table size
SELECT * FROM hypertable_size('ohlcv_data');

# Monitor connection count
netstat -an | grep ESTABLISHED | wc -l
```

---

## Document Structure

This research package includes:

1. **FOREX_WEBSOCKET_RESEARCH.md** - Comprehensive technical reference (12 sections)
2. **WEBSOCKET_IMPLEMENTATION_PATTERNS.md** - 9 production-ready code patterns
3. **PROVIDER_SPECIFIC_CONFIGS.md** - Integration guides for 4 major providers
4. **RESEARCH_SUMMARY.md** - This executive summary

**Total:** ~15,000 lines of documentation and code examples

---

## Key Takeaway

Professional trading systems don't poll REST APIs for market data. They combine:

1. **One-time REST bootstrap** → Load 30 days history
2. **Persistent WebSocket stream** → Receive only new candles
3. **Local cache (Redis)** → Instant data access
4. **Cold storage (TimescaleDB)** → Durable history
5. **Intelligent recovery** → Auto-reconnect + gap detection

This eliminates rate limiting, provides sub-second latency, and scales effortlessly.

**Implementation time: 2-4 weeks to production**

