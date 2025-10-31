"""
Trading Database Manager

SQLite database for persistent storage of all trading data:
- Positions (open and closed)
- Trades with complete reasoning
- Signals generated
- Agent analysis history
- Technical indicators
- Performance metrics
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import pandas as pd
from contextlib import contextmanager


class TradingDatabase:
    """Manages all trading data persistence in SQLite."""

    def __init__(self, db_path: str = "trading_data.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        """Create all database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Positions table (open and closed)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    units REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    current_price REAL,
                    unrealized_pl REAL,
                    status TEXT DEFAULT 'OPEN',
                    signal_confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Trades table (completed)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    position_id TEXT,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    units REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP NOT NULL,
                    realized_pl REAL NOT NULL,
                    realized_pl_pips REAL NOT NULL,
                    exit_reason TEXT NOT NULL,
                    signal_confidence REAL,
                    signal_reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Signals table (all generated signals)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    risk_reward_ratio REAL NOT NULL,
                    pips_risk REAL NOT NULL,
                    pips_reward REAL NOT NULL,
                    reasoning TEXT,
                    indicators TEXT,
                    executed BOOLEAN DEFAULT 0,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Agent analysis history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_analysis (
                    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    trend_primary TEXT,
                    trend_secondary TEXT,
                    price_action_output TEXT,
                    momentum_output TEXT,
                    decision_output TEXT,
                    signal_generated BOOLEAN,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Technical indicators snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    indicators TEXT NOT NULL,
                    hedge_strategies TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Performance metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    unrealized_pl REAL NOT NULL,
                    realized_pl_today REAL NOT NULL,
                    open_positions INTEGER NOT NULL,
                    total_trades INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    profit_factor REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Market data snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    high_1h REAL,
                    low_1h REAL,
                    volume REAL,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_pair ON positions(pair)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals(pair)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_analysis_pair ON agent_analysis(pair)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_analysis_timestamp ON agent_analysis(timestamp)")

            # Run migrations
            self._run_migrations(cursor)

            conn.commit()
            print("✅ Database initialized successfully")

    def _run_migrations(self, cursor):
        """Run database migrations to add new columns."""
        # Add SL/TP calculation tracking columns to signals table
        columns_to_add = [
            ('sl_method', 'TEXT'),  # 'atr', 'support', 'resistance'
            ('tp_method', 'TEXT'),  # 'atr', 'support', 'resistance'
            ('rr_adjusted', 'BOOLEAN DEFAULT 0'),  # Whether RR was adjusted to meet minimum
            ('calculation_steps', 'TEXT'),  # JSON array of calculation steps
            ('atr_value', 'REAL'),  # ATR value used
            ('nearest_support', 'REAL'),  # Support level used
            ('nearest_resistance', 'REAL'),  # Resistance level used
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"""
                    ALTER TABLE signals ADD COLUMN {column_name} {column_type}
                """)
                print(f"  ✓ Added column: signals.{column_name}")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' not in str(e).lower():
                    print(f"  ⚠️  Error adding column {column_name}: {e}")

    # ==================== POSITIONS ====================

    def save_position(self, position_data: Dict):
        """Save or update a position."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO positions (
                    position_id, pair, side, units, entry_price, entry_time,
                    stop_loss, take_profit, current_price, unrealized_pl,
                    status, signal_confidence, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_data['position_id'],
                position_data['pair'],
                position_data['side'],
                position_data['units'],
                position_data['entry_price'],
                position_data['entry_time'],
                position_data['stop_loss'],
                position_data['take_profit'],
                position_data.get('current_price'),
                position_data.get('unrealized_pl', 0.0),
                position_data.get('status', 'OPEN'),
                position_data.get('signal_confidence', 0.0),
                datetime.now()
            ))

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_time DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_position(self, position_id: str) -> Optional[Dict]:
        """Get a specific position."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE position_id = ?", (position_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def close_position(self, position_id: str):
        """Mark position as closed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE positions SET status = 'CLOSED', updated_at = ? WHERE position_id = ?
            """, (datetime.now(), position_id))

    # ==================== TRADES ====================

    def save_trade(self, trade_data: Dict):
        """Save a completed trade."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, position_id, pair, side, units, entry_price, exit_price,
                    stop_loss, take_profit, entry_time, exit_time, realized_pl,
                    realized_pl_pips, exit_reason, signal_confidence, signal_reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data['trade_id'],
                trade_data.get('position_id'),
                trade_data['pair'],
                trade_data['side'],
                trade_data['units'],
                trade_data['entry_price'],
                trade_data['exit_price'],
                trade_data['stop_loss'],
                trade_data['take_profit'],
                trade_data['entry_time'],
                trade_data['exit_time'],
                trade_data['realized_pl'],
                trade_data['realized_pl_pips'],
                trade_data['exit_reason'],
                trade_data.get('signal_confidence', 0.0),
                json.dumps(trade_data.get('signal_reasoning', []))
            ))

    def get_trades(self, limit: int = 100) -> List[Dict]:
        """Get recent trades."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?
            """, (limit,))
            trades = []
            for row in cursor.fetchall():
                trade = dict(row)
                if trade['signal_reasoning']:
                    trade['signal_reasoning'] = json.loads(trade['signal_reasoning'])
                trades.append(trade)
            return trades

    def get_trades_by_pair(self, pair: str, limit: int = 50) -> List[Dict]:
        """Get trades for specific pair."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE pair = ? ORDER BY exit_time DESC LIMIT ?
            """, (pair, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== SIGNALS ====================

    def save_signal(self, signal_data: Dict):
        """Save a generated signal with SL/TP calculation details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (
                    pair, timeframe, signal, confidence, entry_price, stop_loss,
                    take_profit, risk_reward_ratio, pips_risk, pips_reward,
                    reasoning, indicators, executed, timestamp,
                    sl_method, tp_method, rr_adjusted, calculation_steps,
                    atr_value, nearest_support, nearest_resistance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data['pair'],
                signal_data['timeframe'],
                signal_data['signal'],
                signal_data['confidence'],
                signal_data['entry_price'],
                signal_data['stop_loss'],
                signal_data['take_profit'],
                signal_data['risk_reward_ratio'],
                signal_data['pips_risk'],
                signal_data['pips_reward'],
                json.dumps(signal_data.get('reasoning', [])),
                json.dumps(signal_data.get('indicators', {})),
                signal_data.get('executed', False),
                signal_data['timestamp'],
                signal_data.get('sl_method'),
                signal_data.get('tp_method'),
                signal_data.get('rr_adjusted', False),
                json.dumps(signal_data.get('calculation_steps', [])),
                signal_data.get('atr_value'),
                signal_data.get('nearest_support'),
                signal_data.get('nearest_resistance')
            ))
            return cursor.lastrowid

    def mark_signal_executed(self, signal_id: int):
        """Mark signal as executed."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE signals SET executed = 1 WHERE signal_id = ?", (signal_id,))

    def get_signals(self, limit: int = 50) -> List[Dict]:
        """Get recent signals."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            signals = []
            for row in cursor.fetchall():
                signal = dict(row)
                if signal['reasoning']:
                    signal['reasoning'] = json.loads(signal['reasoning'])
                if signal['indicators']:
                    signal['indicators'] = json.loads(signal['indicators'])
                signals.append(signal)
            return signals

    # ==================== AGENT ANALYSIS ====================

    def save_agent_analysis(self, analysis_data: Dict):
        """Save complete agent analysis."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_analysis (
                    pair, timeframe, current_price, trend_primary, trend_secondary,
                    price_action_output, momentum_output, decision_output,
                    signal_generated, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_data['pair'],
                analysis_data['timeframe'],
                analysis_data['current_price'],
                analysis_data.get('trend_primary'),
                analysis_data.get('trend_secondary'),
                json.dumps(analysis_data.get('price_action', {})),
                json.dumps(analysis_data.get('momentum', {})),
                json.dumps(analysis_data.get('decision', {})),
                analysis_data.get('signal_generated', False),
                analysis_data['timestamp']
            ))

    def get_agent_analysis(self, pair: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get agent analysis history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if pair:
                cursor.execute("""
                    SELECT * FROM agent_analysis WHERE pair = ? ORDER BY timestamp DESC LIMIT ?
                """, (pair, limit))
            else:
                cursor.execute("""
                    SELECT * FROM agent_analysis ORDER BY timestamp DESC LIMIT ?
                """, (limit,))

            analyses = []
            for row in cursor.fetchall():
                analysis = dict(row)
                if analysis['price_action_output']:
                    analysis['price_action_output'] = json.loads(analysis['price_action_output'])
                if analysis['momentum_output']:
                    analysis['momentum_output'] = json.loads(analysis['momentum_output'])
                if analysis['decision_output']:
                    analysis['decision_output'] = json.loads(analysis['decision_output'])
                analyses.append(analysis)
            return analyses

    # ==================== TECHNICAL INDICATORS ====================

    def save_indicators(self, indicator_data: Dict):
        """Save technical indicators snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO technical_indicators (
                    pair, timeframe, indicators, hedge_strategies, timestamp
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                indicator_data['pair'],
                indicator_data['timeframe'],
                json.dumps(indicator_data['indicators']),
                json.dumps(indicator_data.get('hedge_strategies', {})),
                indicator_data['timestamp']
            ))

    def get_latest_indicators(self, pair: str) -> Optional[Dict]:
        """Get latest indicators for a pair."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM technical_indicators WHERE pair = ? ORDER BY timestamp DESC LIMIT 1
            """, (pair,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data['indicators'] = json.loads(data['indicators'])
                if data['hedge_strategies']:
                    data['hedge_strategies'] = json.loads(data['hedge_strategies'])
                return data
            return None

    # ==================== PERFORMANCE METRICS ====================

    def save_performance_metrics(self, metrics: Dict):
        """Save performance snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_metrics (
                    balance, equity, unrealized_pl, realized_pl_today, open_positions,
                    total_trades, win_rate, profit_factor, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics['balance'],
                metrics['equity'],
                metrics['unrealized_pl'],
                metrics['realized_pl_today'],
                metrics['open_positions'],
                metrics['total_trades'],
                metrics['win_rate'],
                metrics['profit_factor'],
                metrics['timestamp']
            ))

    def get_performance_history(self, hours: int = 24) -> List[Dict]:
        """Get performance metrics for last N hours."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM performance_metrics
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp ASC
            """, (hours,))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== MARKET DATA ====================

    def save_market_data(self, market_data: Dict):
        """Save market data snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO market_data (
                    pair, current_price, high_1h, low_1h, volume, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                market_data['pair'],
                market_data['current_price'],
                market_data.get('high_1h'),
                market_data.get('low_1h'),
                market_data.get('volume'),
                market_data['timestamp']
            ))

    def get_latest_market_data(self, pair: str) -> Optional[Dict]:
        """Get latest market data for pair."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM market_data WHERE pair = ? ORDER BY timestamp DESC LIMIT 1
            """, (pair,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== STATISTICS ====================

    def get_statistics(self) -> Dict:
        """Get comprehensive statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total trades
            cursor.execute("SELECT COUNT(*) as total FROM trades")
            total_trades = cursor.fetchone()['total']

            # Win/Loss stats
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN realized_pl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN realized_pl < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(realized_pl) as total_pl,
                    AVG(CASE WHEN realized_pl > 0 THEN realized_pl END) as avg_win,
                    AVG(CASE WHEN realized_pl < 0 THEN realized_pl END) as avg_loss
                FROM trades
            """)
            stats = dict(cursor.fetchone())

            # Open positions
            cursor.execute("SELECT COUNT(*) as open FROM positions WHERE status = 'OPEN'")
            open_positions = cursor.fetchone()['open']

            # Calculate metrics
            wins = stats['wins'] or 0
            losses = stats['losses'] or 0
            avg_win = stats['avg_win'] or 0
            avg_loss = stats['avg_loss'] or 0

            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            profit_factor = (abs(avg_win * wins) / abs(avg_loss * losses)) if losses > 0 and avg_loss != 0 else 0

            return {
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': stats['total_pl'] or 0,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'open_positions': open_positions
            }

    def get_recent_signals(self, limit: int = 50, pair: Optional[str] = None) -> List[Dict]:
        """
        Get recent trading signals.

        Args:
            limit: Maximum number of signals to return
            pair: Optional filter by currency pair

        Returns:
            List of signal dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    signal_id, pair, timeframe, signal, confidence,
                    entry_price, stop_loss, take_profit, risk_reward,
                    reasoning, timestamp
                FROM signals
            """

            if pair:
                query += " WHERE pair = ?"
                cursor.execute(query + " ORDER BY timestamp DESC LIMIT ?", (pair, limit))
            else:
                cursor.execute(query + " ORDER BY timestamp DESC LIMIT ?", (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ==================== UTILITIES ====================

    def export_to_csv(self, table: str, filepath: str):
        """Export table to CSV."""
        with self.get_connection() as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            df.to_csv(filepath, index=False)
            print(f"✅ Exported {table} to {filepath}")

    def vacuum(self):
        """Optimize database."""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            print("✅ Database optimized")


# Singleton instance
_db_instance = None

def get_database() -> TradingDatabase:
    """Get database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = TradingDatabase()
    return _db_instance
