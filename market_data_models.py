"""
Shared Market Data Models

Dataclasses used across all components for consistent data exchange
between WebSocket collectors, DataBento, DataHub, and UnifiedDataFetcher.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Tick:
    """Real-time tick/quote data."""
    symbol: str
    bid: float
    ask: float
    mid: float
    spread: float  # in pips
    timestamp: datetime

    def __post_init__(self):
        """Calculate derived fields if not provided."""
        if self.mid == 0.0 and self.bid > 0 and self.ask > 0:
            self.mid = (self.bid + self.ask) / 2.0

        if self.spread == 0.0 and self.bid > 0 and self.ask > 0:
            # Calculate spread in pips
            pip_value = 0.01 if 'JPY' in self.symbol else 0.0001
            self.spread = (self.ask - self.bid) / pip_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'mid': self.mid,
            'spread': self.spread,
            'timestamp': self.timestamp.isoformat()
        }

    def is_stale(self, max_age_seconds: int = 2) -> bool:
        """Check if tick is stale (older than max_age_seconds)."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > max_age_seconds


@dataclass
class Candle:
    """OHLC candle data."""
    symbol: str
    timestamp: datetime  # Open time of candle
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    # Source metadata (for multi-source data integration)
    source: str = "IG"  # "IG" or "DATABENTO"
    volume_type: str = "tick"  # "tick" (proxy) or "real" (actual volume)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'source': self.source,
            'volume_type': self.volume_type
        }

    def is_complete(self) -> bool:
        """Check if candle has valid OHLC data."""
        return all([
            self.open > 0,
            self.high > 0,
            self.low > 0,
            self.close > 0,
            self.high >= self.low,
            self.high >= self.open,
            self.high >= self.close,
            self.low <= self.open,
            self.low <= self.close
        ])


@dataclass
class OrderFlowMetrics:
    """
    Order flow and market microstructure metrics from CME futures.

    Calculated from Level 2 order book (MBP-10) and trade data.
    Provides insight into institutional order flow and market pressure.
    """
    symbol: str  # Spot pair (EUR_USD, GBP_USD, etc.)
    futures_symbol: str  # Futures contract (6E, 6B, etc.)
    timestamp: datetime
    window_seconds: int = 60  # Rolling window size

    # Order Flow Imbalance (OFI)
    ofi_60s: float = 0.0  # Cumulative OFI over 60s window

    # Volume metrics
    net_volume_delta: float = 0.0  # Buy volume - Sell volume
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    total_volume: float = 0.0

    # Top of book metrics
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    bid_size: float = 0.0
    ask_size: float = 0.0
    top_of_book_imbalance: float = 0.0  # (bid_size - ask_size) / (bid_size + ask_size)

    # Sweep detection
    buy_sweep_count: int = 0  # Aggressive buys through ask
    sell_sweep_count: int = 0  # Aggressive sells through bid

    # Price metrics
    vwap_60s: Optional[float] = None  # Volume-weighted average price

    # Derived signals
    order_flow_bias: str = "neutral"  # "bullish", "bearish", "neutral"
    toxicity_score: float = 0.0  # VPIN-style toxicity (0-1)

    # Metadata
    updates_count: int = 0  # Number of updates in window
    is_stale: bool = False

    def __post_init__(self):
        """Calculate derived fields."""
        # Calculate top-of-book imbalance
        if self.bid_size > 0 or self.ask_size > 0:
            total_size = self.bid_size + self.ask_size
            if total_size > 0:
                self.top_of_book_imbalance = (self.bid_size - self.ask_size) / total_size

        # Determine order flow bias
        if self.net_volume_delta > 0 and self.ofi_60s > 0:
            self.order_flow_bias = "bullish"
        elif self.net_volume_delta < 0 and self.ofi_60s < 0:
            self.order_flow_bias = "bearish"
        else:
            self.order_flow_bias = "neutral"

        # Calculate toxicity score (simplified VPIN)
        # Higher toxicity = more informed trading = higher risk
        if self.total_volume > 0:
            volume_imbalance = abs(self.net_volume_delta) / self.total_volume
            self.toxicity_score = min(volume_imbalance, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'futures_symbol': self.futures_symbol,
            'timestamp': self.timestamp.isoformat(),
            'window_seconds': self.window_seconds,
            'ofi_60s': self.ofi_60s,
            'net_volume_delta': self.net_volume_delta,
            'buy_volume': self.buy_volume,
            'sell_volume': self.sell_volume,
            'total_volume': self.total_volume,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'top_of_book_imbalance': self.top_of_book_imbalance,
            'buy_sweep_count': self.buy_sweep_count,
            'sell_sweep_count': self.sell_sweep_count,
            'vwap_60s': self.vwap_60s,
            'order_flow_bias': self.order_flow_bias,
            'toxicity_score': self.toxicity_score,
            'updates_count': self.updates_count,
            'is_stale': self.is_stale
        }

    def check_staleness(self, max_age_seconds: int = 5) -> bool:
        """Check if metrics are stale."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        self.is_stale = age > max_age_seconds
        return self.is_stale


@dataclass
class MarketDataSnapshot:
    """
    Complete market data snapshot for a symbol.

    Aggregates all data types for a single point in time.
    Used by UnifiedDataFetcher to provide complete market picture.
    """
    symbol: str
    timestamp: datetime

    # Price data
    tick: Optional[Tick] = None
    candles: list = field(default_factory=list)  # List of Candle objects

    # Order flow
    order_flow: Optional[OrderFlowMetrics] = None

    # Technical indicators (calculated separately)
    indicators: Optional[Dict[str, Any]] = None

    # Metadata
    data_quality: str = "good"  # "good", "partial", "stale", "missing"
    missing_components: list = field(default_factory=list)

    def __post_init__(self):
        """Validate data quality."""
        self.missing_components = []

        if self.tick is None:
            self.missing_components.append("tick")
        elif self.tick.is_stale():
            self.data_quality = "stale"

        if not self.candles or len(self.candles) == 0:
            self.missing_components.append("candles")

        if self.order_flow is None:
            self.missing_components.append("order_flow")
        elif self.order_flow.is_stale:
            self.data_quality = "stale"

        if len(self.missing_components) > 1:
            self.data_quality = "missing"
        elif len(self.missing_components) == 1:
            self.data_quality = "partial"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'tick': self.tick.to_dict() if self.tick else None,
            'candles': [c.to_dict() for c in self.candles],
            'order_flow': self.order_flow.to_dict() if self.order_flow else None,
            'indicators': self.indicators,
            'data_quality': self.data_quality,
            'missing_components': self.missing_components
        }
