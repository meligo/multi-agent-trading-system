"""
Order Book L2 (Level 2) - Top 10 Levels
Maintains real-time order book state from DataBento MBP-10 updates

Provides:
- Best bid/ask tracking
- Microprice calculation
- Queue imbalance
- Order Flow Imbalance (OFI)
- Depth analysis
"""

import logging
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class BookLevel:
    """Single price level in the order book."""
    price: float
    size: float


class OrderBookL2:
    """
    Maintains top 10 levels of bids and asks from MBP-10 data.

    Internal state:
    - bids: [(price, size), ...] sorted high to low
    - asks: [(price, size), ...] sorted low to high
    """

    def __init__(self, symbol: str, snapshot_interval_ms: int = 250):
        """
        Initialize order book.

        Args:
            symbol: Trading symbol (e.g., '6E')
            snapshot_interval_ms: How often to generate snapshots (ms)
        """
        self.symbol = symbol

        # Order book levels
        self.bids: List[Tuple[float, float]] = []  # [(price, size), ...] high to low
        self.asks: List[Tuple[float, float]] = []  # [(price, size), ...] low to high

        # Last update timestamp
        self.last_update_ts: Optional[datetime] = None

        # Snapshot generation
        self.snapshot_interval = timedelta(milliseconds=snapshot_interval_ms)
        self.last_snapshot_ts: Optional[datetime] = None

        # Sequence tracking
        self.last_sequence: int = 0

        # Historical state for OFI calculation
        self.prev_bids: List[Tuple[float, float]] = []
        self.prev_asks: List[Tuple[float, float]] = []

        logger.debug(f"OrderBookL2 initialized for {symbol}")

    def update(self, record):
        """
        Update order book from MBP-10 record.

        Args:
            record: DataBento MBP-10 record
        """
        # Check sequence
        if record.sequence <= self.last_sequence:
            logger.warning(f"Out-of-order sequence: {record.sequence} <= {self.last_sequence}")
            return

        self.last_sequence = record.sequence
        self.last_update_ts = datetime.utcnow()

        # Save previous state for OFI
        self.prev_bids = self.bids.copy()
        self.prev_asks = self.asks.copy()

        # Extract bids (sorted high to low)
        new_bids = []
        for i in range(10):
            price = getattr(record, f'bid_px_{i:02d}', 0)
            size = getattr(record, f'bid_sz_{i:02d}', 0)
            if price > 0 and size > 0:
                new_bids.append((price, size))

        # Extract asks (sorted low to high)
        new_asks = []
        for i in range(10):
            price = getattr(record, f'ask_px_{i:02d}', 0)
            size = getattr(record, f'ask_sz_{i:02d}', 0)
            if price > 0 and size > 0:
                new_asks.append((price, size))

        # Update state
        self.bids = sorted(new_bids, key=lambda x: x[0], reverse=True)[:10]
        self.asks = sorted(new_asks, key=lambda x: x[0])[:10]

    # ========================================================================
    # BOOK QUERIES
    # ========================================================================

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return self.asks[0][0] if self.asks else None

    @property
    def mid(self) -> Optional[float]:
        """Get mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Get bid-ask spread in basis points."""
        if self.spread and self.mid:
            return (self.spread / self.mid) * 10000
        return None

    # ========================================================================
    # MICROSTRUCTURE FEATURES
    # ========================================================================

    def microprice(self) -> Optional[float]:
        """
        Calculate microprice (volume-weighted mid price).

        Formula: (best_ask * bid_sz + best_bid * ask_sz) / (bid_sz + ask_sz)

        This is a better estimate of "true" mid than simple (bid+ask)/2
        because it accounts for size imbalance.
        """
        if not self.bids or not self.asks:
            return None

        best_bid, bid_sz = self.bids[0]
        best_ask, ask_sz = self.asks[0]

        if bid_sz + ask_sz == 0:
            return self.mid

        return (best_ask * bid_sz + best_bid * ask_sz) / (bid_sz + ask_sz)

    def queue_imbalance(self, n_levels: int = 1) -> Optional[float]:
        """
        Calculate queue imbalance for top N levels.

        Formula: (total_bid_size - total_ask_size) / (total_bid_size + total_ask_size)

        Returns:
            Imbalance in [-1, 1] range
            - Positive: more bids (bullish pressure)
            - Negative: more asks (bearish pressure)
        """
        if not self.bids or not self.asks:
            return None

        bid_total = sum(size for _, size in self.bids[:n_levels])
        ask_total = sum(size for _, size in self.asks[:n_levels])

        if bid_total + ask_total == 0:
            return 0.0

        return (bid_total - ask_total) / (bid_total + ask_total)

    def depth_imbalance(self, n_levels: int = 10) -> Optional[float]:
        """
        Calculate depth imbalance across N levels.

        Similar to queue_imbalance but uses all N levels.
        """
        return self.queue_imbalance(n_levels=n_levels)

    def order_flow_imbalance(self) -> float:
        """
        Calculate Order Flow Imbalance (OFI).

        OFI measures aggressive buying vs selling pressure by tracking
        changes in order book depth.

        Formula:
        - If bid price unchanged: Δbid_size
        - If ask price unchanged: Δask_size
        - Sum over all levels

        Returns:
            OFI value (positive = buying pressure, negative = selling pressure)
        """
        if not self.prev_bids or not self.prev_asks:
            return 0.0

        ofi = 0.0

        # Bid side OFI
        for i in range(min(len(self.bids), len(self.prev_bids))):
            curr_price, curr_size = self.bids[i]
            prev_price, prev_size = self.prev_bids[i]

            if curr_price == prev_price:
                # Price unchanged, size change indicates flow
                ofi += (curr_size - prev_size)

        # Ask side OFI (subtract because asks are negative pressure)
        for i in range(min(len(self.asks), len(self.prev_asks))):
            curr_price, curr_size = self.asks[i]
            prev_price, prev_size = self.prev_asks[i]

            if curr_price == prev_price:
                # Price unchanged, size change indicates flow
                ofi -= (curr_size - prev_size)

        return ofi

    def total_depth(self, n_levels: int = 10) -> Tuple[float, float]:
        """
        Get total depth on bid and ask sides.

        Args:
            n_levels: Number of levels to sum

        Returns:
            (total_bid_size, total_ask_size)
        """
        bid_depth = sum(size for _, size in self.bids[:n_levels])
        ask_depth = sum(size for _, size in self.asks[:n_levels])
        return (bid_depth, ask_depth)

    # ========================================================================
    # SNAPSHOT MANAGEMENT
    # ========================================================================

    def should_generate_snapshot(self) -> bool:
        """
        Check if it's time to generate a snapshot.

        Returns:
            True if snapshot interval has elapsed
        """
        if self.last_snapshot_ts is None:
            self.last_snapshot_ts = datetime.utcnow()
            return True

        elapsed = datetime.utcnow() - self.last_snapshot_ts

        if elapsed >= self.snapshot_interval:
            self.last_snapshot_ts = datetime.utcnow()
            return True

        return False

    # ========================================================================
    # DEBUGGING
    # ========================================================================

    def print_book(self, n_levels: int = 5):
        """Print current book state (for debugging)."""
        print(f"\n{self.symbol} Order Book (Top {n_levels}):")
        print("=" * 50)
        print(f"{'ASK':>20} | {'BID':>20}")
        print("-" * 50)

        for i in range(n_levels):
            ask_str = f"{self.asks[i][0]:.5f} @ {self.asks[i][1]:.0f}" if i < len(self.asks) else ""
            bid_str = f"{self.bids[i][0]:.5f} @ {self.bids[i][1]:.0f}" if i < len(self.bids) else ""
            print(f"{ask_str:>20} | {bid_str:>20}")

        print("-" * 50)
        print(f"Mid: {self.mid:.5f} | Spread: {self.spread:.5f} ({self.spread_bps:.1f} bps)")
        print(f"Microprice: {self.microprice():.5f}")
        print(f"Queue Imbalance (1): {self.queue_imbalance(1):.3f}")
        print(f"Queue Imbalance (5): {self.queue_imbalance(5):.3f}")
        print(f"OFI: {self.order_flow_imbalance():.2f}")
        print("=" * 50)

    def to_dict(self) -> dict:
        """Export book state as dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.last_update_ts.isoformat() if self.last_update_ts else None,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid": self.mid,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "microprice": self.microprice(),
            "queue_imbalance_1": self.queue_imbalance(1),
            "queue_imbalance_5": self.queue_imbalance(5),
            "depth_imbalance": self.depth_imbalance(),
            "ofi": self.order_flow_imbalance(),
            "total_bid_depth": self.total_depth()[0],
            "total_ask_depth": self.total_depth()[1],
            "bids": self.bids[:5],  # Top 5 levels
            "asks": self.asks[:5],
        }


# ============================================================================
# TESTING
# ============================================================================

def test_order_book():
    """Test order book functionality with synthetic data."""
    book = OrderBookL2("TEST")

    # Mock record class
    class MockRecord:
        def __init__(self, seq):
            self.sequence = seq
            # Bids
            self.bid_px_00 = 1.1000
            self.bid_sz_00 = 100
            self.bid_px_01 = 1.0999
            self.bid_sz_01 = 150
            self.bid_px_02 = 1.0998
            self.bid_sz_02 = 200
            # Asks
            self.ask_px_00 = 1.1001
            self.ask_sz_00 = 80
            self.ask_px_01 = 1.1002
            self.ask_sz_01 = 120
            self.ask_px_02 = 1.1003
            self.ask_sz_02 = 180

    # Update with mock data
    record = MockRecord(1)
    book.update(record)

    # Print results
    book.print_book(3)

    # Test features
    assert book.best_bid == 1.1000
    assert book.best_ask == 1.1001
    assert abs(book.mid - 1.10005) < 1e-6
    assert book.microprice() is not None
    assert book.queue_imbalance(1) > 0  # More bids than asks

    print("\n✅ Order book tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_order_book()
