-- ==============================================================================
-- Finnhub Technical Analysis Data - Schema Extension
-- ==============================================================================
--
-- This extends the main schema to support Finnhub technical analysis data:
-- - Aggregate indicators (consensus from 30+ TAs)
-- - Pattern recognition (chart patterns)
-- - Support/resistance levels
-- - Candle data (OHLCV)
--
-- ==============================================================================

-- Finnhub Aggregate Indicators: Consensus signals from 30+ technical indicators
CREATE TABLE IF NOT EXISTS finnhub_aggregate_indicators (
    provider_event_ts TIMESTAMPTZ NOT NULL,
    recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    timeframe TEXT NOT NULL, -- 'D', 'W', 'M' (daily, weekly, monthly)
    buy_count INTEGER NOT NULL,
    sell_count INTEGER NOT NULL,
    neutral_count INTEGER NOT NULL,
    total_indicators INTEGER NOT NULL,
    consensus TEXT NOT NULL, -- 'BULLISH', 'BEARISH', 'NEUTRAL'
    confidence DOUBLE PRECISION NOT NULL, -- 0-1
    signal TEXT NOT NULL, -- Overall Finnhub signal ('buy', 'sell', 'neutral')
    adx DOUBLE PRECISION, -- Trend strength
    trending BOOLEAN, -- Is market trending?
    extras JSONB -- Additional technical analysis data
);

-- Create hypertable for Finnhub aggregate indicators
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'finnhub_aggregate_indicators'
    ) THEN
        PERFORM create_hypertable('finnhub_aggregate_indicators', 'provider_event_ts',
            chunk_time_interval => INTERVAL '1 day'
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_finnhub_agg_instrument ON finnhub_aggregate_indicators(instrument_id, provider_event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_finnhub_agg_consensus ON finnhub_aggregate_indicators(consensus, provider_event_ts DESC);

-- Finnhub Patterns: Detected chart patterns
CREATE TABLE IF NOT EXISTS finnhub_patterns (
    provider_event_ts TIMESTAMPTZ NOT NULL,
    recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    timeframe TEXT NOT NULL, -- 'D', 'W', 'M'
    pattern_type TEXT NOT NULL, -- 'double_top', 'head_shoulders', 'triangle', etc.
    direction TEXT NOT NULL, -- 'bullish' or 'bearish'
    confidence DOUBLE PRECISION NOT NULL, -- 0-1
    start_time TIMESTAMPTZ, -- When pattern started forming
    end_time TIMESTAMPTZ, -- When pattern completed
    extras JSONB
);

-- Create hypertable for Finnhub patterns
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'finnhub_patterns'
    ) THEN
        PERFORM create_hypertable('finnhub_patterns', 'provider_event_ts',
            chunk_time_interval => INTERVAL '1 day'
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_finnhub_patterns_instrument ON finnhub_patterns(instrument_id, provider_event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_finnhub_patterns_type ON finnhub_patterns(pattern_type, provider_event_ts DESC);

-- Finnhub Support/Resistance: Pre-calculated S/R levels
CREATE TABLE IF NOT EXISTS finnhub_support_resistance (
    provider_event_ts TIMESTAMPTZ NOT NULL,
    recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    level_type TEXT NOT NULL, -- 'support' or 'resistance'
    price_level DOUBLE PRECISION NOT NULL,
    strength DOUBLE PRECISION, -- Optional: 0-1 strength score
    extras JSONB
);

-- Create hypertable for Finnhub S/R
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'finnhub_support_resistance'
    ) THEN
        PERFORM create_hypertable('finnhub_support_resistance', 'provider_event_ts',
            chunk_time_interval => INTERVAL '1 day'
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_finnhub_sr_instrument ON finnhub_support_resistance(instrument_id, provider_event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_finnhub_sr_type ON finnhub_support_resistance(level_type, instrument_id, provider_event_ts DESC);

-- Finnhub Candles: OHLCV data from Finnhub API (fallback data source)
CREATE TABLE IF NOT EXISTS finnhub_candles (
    provider_event_ts TIMESTAMPTZ NOT NULL,
    recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    timeframe TEXT NOT NULL, -- '1', '5', '15', '60', 'D', 'W', 'M'
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    extras JSONB
);

-- Create hypertable for Finnhub candles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'finnhub_candles'
    ) THEN
        PERFORM create_hypertable('finnhub_candles', 'provider_event_ts',
            chunk_time_interval => INTERVAL '1 day'
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_finnhub_candles_instrument ON finnhub_candles(instrument_id, timeframe, provider_event_ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_finnhub_candles_dedupe ON finnhub_candles(instrument_id, timeframe, provider_event_ts);

-- ==============================================================================
-- IG Candles (WebSocket data) - Not in main schema
-- ==============================================================================

CREATE TABLE IF NOT EXISTS ig_candles (
    provider_event_ts TIMESTAMPTZ NOT NULL,
    recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    timeframe TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    source TEXT NOT NULL,
    extras JSONB
);

-- Create hypertable for IG candles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'ig_candles'
    ) THEN
        PERFORM create_hypertable('ig_candles', 'provider_event_ts',
            chunk_time_interval => INTERVAL '1 day'
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ig_candles_instrument ON ig_candles(instrument_id, timeframe, provider_event_ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ig_candles_dedupe ON ig_candles(instrument_id, timeframe, provider_event_ts);

-- ==============================================================================
-- TIMESCALEDB COMPRESSION POLICIES (Optional)
-- ==============================================================================

-- Compress Finnhub data after 7 days (it's not high-frequency)
-- SELECT add_compression_policy('finnhub_aggregate_indicators', INTERVAL '7 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('finnhub_patterns', INTERVAL '7 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('finnhub_support_resistance', INTERVAL '7 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('finnhub_candles', INTERVAL '7 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('ig_candles', INTERVAL '7 days', if_not_exists => TRUE);
