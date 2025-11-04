"""
Agent Data Logger

Captures ALL data sent to agents, indicators, and agent responses for later analysis.
Stores comprehensive snapshots of every analysis cycle.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import psycopg
from psycopg.rows import dict_row
from logging_config import setup_file_logging

logger = setup_file_logging("agent_data_logger", console_output=False)


@dataclass
class AnalysisSession:
    """Main analysis session record."""
    session_id: str
    pair: str
    timestamp: datetime
    current_price: float
    spread_pips: float
    trading_hours: bool
    can_trade: bool


@dataclass
class MarketSnapshot:
    """Complete market data snapshot."""
    session_id: str
    pair: str
    timestamp: datetime

    # OHLCV data (last 50 bars)
    candles_json: str  # JSON array of candles

    # Current market state
    current_price: float
    bid: float
    ask: float
    spread: float

    # Support/Resistance
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]


@dataclass
class IndicatorValues:
    """All calculated indicator values."""
    session_id: str
    pair: str
    timestamp: datetime

    # EMA Ribbon (3, 6, 12)
    ema_3: Optional[float]
    ema_6: Optional[float]
    ema_12: Optional[float]
    ema_alignment: Optional[str]  # "BULLISH", "BEARISH", "NEUTRAL"

    # RSI (14)
    rsi: Optional[float]
    rsi_zone: Optional[str]  # "OVERBOUGHT", "OVERSOLD", "NEUTRAL"

    # MACD
    macd: Optional[float]
    macd_signal: Optional[float]
    macd_histogram: Optional[float]
    macd_cross: Optional[str]  # "BULLISH", "BEARISH", "NONE"

    # Bollinger Bands (20, 2)
    bb_upper: Optional[float]
    bb_middle: Optional[float]
    bb_lower: Optional[float]
    bb_width: Optional[float]
    price_position: Optional[str]  # "ABOVE_UPPER", "BELOW_LOWER", "INSIDE"

    # Volume
    volume_ma: Optional[float]
    volume_surge: Optional[bool]

    # Momentum
    momentum_strength: Optional[float]
    momentum_direction: Optional[str]  # "UP", "DOWN", "FLAT"

    # ATR for volatility
    atr: Optional[float]
    atr_pips: Optional[float]


@dataclass
class AgentResponse:
    """Individual agent response."""
    session_id: str
    agent_name: str  # "fast_momentum", "technical", "aggressive_risk", "conservative_risk"
    timestamp: datetime

    # Response content
    response_json: str  # Full JSON response from agent

    # Extracted key fields
    recommendation: Optional[str]
    confidence: Optional[float]
    reasoning: Optional[str]

    # Execution time
    execution_time_ms: Optional[float]


@dataclass
class JudgeDecision:
    """Judge decision (Scalp Validator or Risk Manager)."""
    session_id: str
    judge_name: str  # "scalp_validator", "risk_manager"
    timestamp: datetime

    # Decision
    approved: bool
    decision_json: str  # Full decision object

    # Key fields
    direction: Optional[str]  # "BUY", "SELL", "NONE"
    entry_price: Optional[float]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    position_size: Optional[float]
    confidence: Optional[float]
    risk_tier: Optional[int]

    # Reasoning
    reasoning: Optional[str]

    # Execution time
    execution_time_ms: Optional[float]


class AgentDataLogger:
    """
    Logs all agent data to database.

    Captures:
    - Market data snapshots
    - All calculated indicators
    - Agent responses
    - Judge decisions
    - Final trade outcomes
    """

    def __init__(self, connection_string: str):
        """Initialize logger with database connection."""
        self.connection_string = connection_string
        self._ensure_tables()
        logger.info("✅ AgentDataLogger initialized")

    def _get_connection(self):
        """Get database connection."""
        return psycopg.connect(
            self.connection_string,
            row_factory=dict_row
        )

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        logger.info("Creating agent data tables...")

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Analysis sessions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_sessions (
                        session_id VARCHAR(100) PRIMARY KEY,
                        pair VARCHAR(20) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        current_price DECIMAL(12, 6),
                        spread_pips DECIMAL(8, 2),
                        trading_hours BOOLEAN,
                        can_trade BOOLEAN,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Market snapshots table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS market_snapshots (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) NOT NULL REFERENCES analysis_sessions(session_id),
                        pair VARCHAR(20) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        candles_json TEXT,
                        current_price DECIMAL(12, 6),
                        bid DECIMAL(12, 6),
                        ask DECIMAL(12, 6),
                        spread DECIMAL(8, 2),
                        nearest_support DECIMAL(12, 6),
                        nearest_resistance DECIMAL(12, 6),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Indicator values table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS indicator_values (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) NOT NULL REFERENCES analysis_sessions(session_id),
                        pair VARCHAR(20) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,

                        -- EMA Ribbon
                        ema_3 DECIMAL(12, 6),
                        ema_6 DECIMAL(12, 6),
                        ema_12 DECIMAL(12, 6),
                        ema_alignment VARCHAR(20),

                        -- RSI
                        rsi DECIMAL(8, 2),
                        rsi_zone VARCHAR(20),

                        -- MACD
                        macd DECIMAL(12, 6),
                        macd_signal DECIMAL(12, 6),
                        macd_histogram DECIMAL(12, 6),
                        macd_cross VARCHAR(20),

                        -- Bollinger Bands
                        bb_upper DECIMAL(12, 6),
                        bb_middle DECIMAL(12, 6),
                        bb_lower DECIMAL(12, 6),
                        bb_width DECIMAL(12, 6),
                        price_position VARCHAR(20),

                        -- Volume
                        volume_ma DECIMAL(16, 2),
                        volume_surge BOOLEAN,

                        -- Momentum
                        momentum_strength DECIMAL(8, 4),
                        momentum_direction VARCHAR(20),

                        -- ATR
                        atr DECIMAL(12, 6),
                        atr_pips DECIMAL(8, 2),

                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Agent responses table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_responses (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) NOT NULL REFERENCES analysis_sessions(session_id),
                        agent_name VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        response_json TEXT NOT NULL,
                        recommendation VARCHAR(20),
                        confidence DECIMAL(5, 4),
                        reasoning TEXT,
                        execution_time_ms DECIMAL(10, 2),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Judge decisions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS judge_decisions (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) NOT NULL REFERENCES analysis_sessions(session_id),
                        judge_name VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        approved BOOLEAN NOT NULL,
                        decision_json TEXT NOT NULL,
                        direction VARCHAR(10),
                        entry_price DECIMAL(12, 6),
                        take_profit DECIMAL(12, 6),
                        stop_loss DECIMAL(12, 6),
                        position_size DECIMAL(10, 4),
                        confidence DECIMAL(5, 4),
                        risk_tier INTEGER,
                        reasoning TEXT,
                        execution_time_ms DECIMAL(10, 2),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Create indexes for faster queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analysis_sessions_timestamp
                    ON analysis_sessions(timestamp DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analysis_sessions_pair
                    ON analysis_sessions(pair, timestamp DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_agent_responses_session
                    ON agent_responses(session_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_judge_decisions_session
                    ON judge_decisions(session_id)
                """)

                conn.commit()

        logger.info("✅ Agent data tables created")

    def log_analysis_session(self, session: AnalysisSession):
        """Log analysis session start."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO analysis_sessions
                        (session_id, pair, timestamp, current_price, spread_pips, trading_hours, can_trade)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        session.session_id,
                        session.pair,
                        session.timestamp,
                        session.current_price,
                        session.spread_pips,
                        session.trading_hours,
                        session.can_trade
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log analysis session: {e}")

    def log_market_snapshot(self, snapshot: MarketSnapshot):
        """Log complete market data snapshot."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO market_snapshots
                        (session_id, pair, timestamp, candles_json, current_price, bid, ask,
                         spread, nearest_support, nearest_resistance)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        snapshot.session_id,
                        snapshot.pair,
                        snapshot.timestamp,
                        snapshot.candles_json,
                        snapshot.current_price,
                        snapshot.bid,
                        snapshot.ask,
                        snapshot.spread,
                        snapshot.nearest_support,
                        snapshot.nearest_resistance
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log market snapshot: {e}")

    def log_indicators(self, indicators: IndicatorValues):
        """Log all calculated indicators."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO indicator_values
                        (session_id, pair, timestamp,
                         ema_3, ema_6, ema_12, ema_alignment,
                         rsi, rsi_zone,
                         macd, macd_signal, macd_histogram, macd_cross,
                         bb_upper, bb_middle, bb_lower, bb_width, price_position,
                         volume_ma, volume_surge,
                         momentum_strength, momentum_direction,
                         atr, atr_pips)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        indicators.session_id,
                        indicators.pair,
                        indicators.timestamp,
                        indicators.ema_3,
                        indicators.ema_6,
                        indicators.ema_12,
                        indicators.ema_alignment,
                        indicators.rsi,
                        indicators.rsi_zone,
                        indicators.macd,
                        indicators.macd_signal,
                        indicators.macd_histogram,
                        indicators.macd_cross,
                        indicators.bb_upper,
                        indicators.bb_middle,
                        indicators.bb_lower,
                        indicators.bb_width,
                        indicators.price_position,
                        indicators.volume_ma,
                        indicators.volume_surge,
                        indicators.momentum_strength,
                        indicators.momentum_direction,
                        indicators.atr,
                        indicators.atr_pips
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log indicators: {e}")

    def log_agent_response(self, response: AgentResponse):
        """Log individual agent response."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO agent_responses
                        (session_id, agent_name, timestamp, response_json,
                         recommendation, confidence, reasoning, execution_time_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        response.session_id,
                        response.agent_name,
                        response.timestamp,
                        response.response_json,
                        response.recommendation,
                        response.confidence,
                        response.reasoning,
                        response.execution_time_ms
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log agent response: {e}")

    def log_judge_decision(self, decision: JudgeDecision):
        """Log judge decision."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO judge_decisions
                        (session_id, judge_name, timestamp, approved, decision_json,
                         direction, entry_price, take_profit, stop_loss, position_size,
                         confidence, risk_tier, reasoning, execution_time_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        decision.session_id,
                        decision.judge_name,
                        decision.timestamp,
                        decision.approved,
                        decision.decision_json,
                        decision.direction,
                        decision.entry_price,
                        decision.take_profit,
                        decision.stop_loss,
                        decision.position_size,
                        decision.confidence,
                        decision.risk_tier,
                        decision.reasoning,
                        decision.execution_time_ms
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log judge decision: {e}")

    def get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Retrieve complete data for an analysis session."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Get session
                    cur.execute("SELECT * FROM analysis_sessions WHERE session_id = %s", (session_id,))
                    session = cur.fetchone()

                    # Get market snapshot
                    cur.execute("SELECT * FROM market_snapshots WHERE session_id = %s", (session_id,))
                    snapshot = cur.fetchone()

                    # Get indicators
                    cur.execute("SELECT * FROM indicator_values WHERE session_id = %s", (session_id,))
                    indicators = cur.fetchone()

                    # Get agent responses
                    cur.execute("SELECT * FROM agent_responses WHERE session_id = %s", (session_id,))
                    agents = cur.fetchall()

                    # Get judge decisions
                    cur.execute("SELECT * FROM judge_decisions WHERE session_id = %s", (session_id,))
                    judges = cur.fetchall()

                    return {
                        'session': session,
                        'snapshot': snapshot,
                        'indicators': indicators,
                        'agents': agents,
                        'judges': judges
                    }
        except Exception as e:
            logger.error(f"Failed to get session data: {e}")
            return {}


if __name__ == "__main__":
    # Test logger initialization
    import os
    from dotenv import load_dotenv

    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        exit(1)

    logger_inst = AgentDataLogger(db_url)
    print("✅ Agent Data Logger initialized successfully")
    print(f"\nTables created:")
    print("  - analysis_sessions")
    print("  - market_snapshots")
    print("  - indicator_values")
    print("  - agent_responses")
    print("  - judge_decisions")
