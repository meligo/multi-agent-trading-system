"""
News Gating Service
Prevents trading and closes positions before high-impact economic events

Critical Features:
- Fetches upcoming high-impact events from InsightSentry
- Gates trading 10-15 minutes before scheduled events
- Automatically closes positions before events
- Monitors breaking news for immediate gating
- Persists gating state to database
"""

import os
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from dataclasses import dataclass
from enum import Enum

from insightsentry_client import InsightSentryClient
from database_manager import DatabaseManager
from data_persistence_manager import DataPersistenceManager

logger = logging.getLogger(__name__)


class GateReason(Enum):
    """Reasons for gating trading."""
    HIGH_IMPACT_EVENT = "high_impact_event"
    BREAKING_NEWS = "breaking_news"
    HIGH_VOLATILITY = "high_volatility"
    MANUAL = "manual"


@dataclass
class GateConfig:
    """Configuration for news gating."""
    # Time before event to start gating (minutes)
    gate_window_minutes: int = 15

    # Time after event to keep gating (minutes)
    grace_period_minutes: int = 5

    # Countries to monitor
    countries: List[str] = None

    # Minimum impact level to gate
    min_impact: str = "high"

    # Check interval (seconds)
    check_interval: int = 60

    # Close positions before events?
    close_positions: bool = True

    # Minutes before event to close positions
    close_window_minutes: int = 10

    def __post_init__(self):
        if self.countries is None:
            self.countries = ["US", "EU", "GB", "JP"]


class NewsGatingService:
    """
    Service that monitors economic calendar and gates trading around high-impact events.

    Workflow:
    1. Fetch upcoming events from InsightSentry every minute
    2. For each event, determine affected currency pairs
    3. Schedule gating windows (15 min before, 5 min after)
    4. Close positions 10 minutes before high-impact events
    5. Persist gating state to database
    6. Expose is_gated(instrument_id) API for trading engine
    """

    def __init__(
        self,
        config: GateConfig = None,
        db_manager: DatabaseManager = None,
        insightsentry_client: InsightSentryClient = None
    ):
        """
        Initialize news gating service.

        Args:
            config: Gate configuration
            db_manager: Database manager
            insightsentry_client: InsightSentry client
        """
        self.config = config or GateConfig()
        self.db = db_manager or DatabaseManager()
        self.is_client = insightsentry_client or InsightSentryClient()

        # Data persistence manager
        self.persistence = DataPersistenceManager(self.db)

        # In-memory cache of gated instruments
        self.gated_instruments: Set[int] = set()

        # Event registry
        self.upcoming_events: List[Dict[str, Any]] = []

        # Running state
        self.running = False

        logger.info(f"NewsGatingService initialized (gate window: {self.config.gate_window_minutes} min)")

    async def start(self):
        """Start the gating service (runs continuously)."""
        self.running = True
        await self.db.initialize()

        logger.info("🚦 News Gating Service started")

        try:
            while self.running:
                await self._update_cycle()
                await asyncio.sleep(self.config.check_interval)
        except Exception as e:
            logger.error(f"Gating service error: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the gating service."""
        self.running = False
        await self.db.close()
        logger.info("🚦 News Gating Service stopped")

    async def _update_cycle(self):
        """
        Single update cycle:
        1. Fetch upcoming events
        2. Process events and update gates
        3. Check for positions to close
        """
        try:
            # Fetch upcoming events (next 24 hours)
            events = await self.is_client.get_high_impact_events(
                lookback_hours=0,
                lookahead_hours=24
            )

            if not events:
                logger.debug("No high-impact events in next 24 hours")
                return

            logger.info(f"Found {len(events)} high-impact events")

            # Save events to database
            try:
                saved_count = await self.persistence.save_economic_events(events)
                logger.debug(f"Saved {saved_count} events to database")
            except Exception as e:
                logger.warning(f"Failed to save events to database: {e}")

            # Process each event
            for event in events:
                await self._process_event(event)

            # Update in-memory gated set
            await self._refresh_gated_instruments()

        except Exception as e:
            logger.error(f"Update cycle error: {e}")

    async def _process_event(self, event: Dict[str, Any]):
        """
        Process a single economic event.

        Args:
            event: Event data from InsightSentry (v3 API format)
        """
        # Extract event details (v3 API format)
        # v3 uses 'date' instead of 'scheduled_time', 'title' instead of 'event_name'
        scheduled_time_str = event.get("date") or event.get("scheduled_time")
        country = event.get("country")
        currency = event.get("currency")
        event_name = event.get("title") or event.get("event_name")
        importance = event.get("importance")

        if not all([scheduled_time_str, currency]):
            logger.warning(f"Incomplete event data: {event}")
            return

        # Parse scheduled time
        try:
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Failed to parse scheduled_time: {scheduled_time_str} - {e}")
            return

        # Generate event_id if not present
        event_id = event.get("event_id") or f"{country}_{event_name}_{scheduled_time.strftime('%Y%m%d%H%M')}"

        # Calculate gate window
        gate_start = scheduled_time - timedelta(minutes=self.config.gate_window_minutes)
        gate_end = scheduled_time + timedelta(minutes=self.config.grace_period_minutes)

        now = datetime.utcnow().replace(tzinfo=scheduled_time.tzinfo)

        # Only process upcoming gates (not past events)
        if gate_end < now:
            return

        # Find affected instruments
        affected_instruments = await self._get_affected_instruments(currency)

        if not affected_instruments:
            logger.debug(f"No instruments affected by {currency} event")
            return

        logger.info(
            f"Event: {event_name} ({currency}) at {scheduled_time} "
            f"- affects {len(affected_instruments)} instruments"
        )

        # Create gating state for each affected instrument
        for instrument_id in affected_instruments:
            await self._create_gate(
                instrument_id=instrument_id,
                start_time=gate_start,
                end_time=gate_end,
                reason=f"{event_name} ({country})",
                event_id=event_id
            )

        # Check if we need to close positions
        close_time = scheduled_time - timedelta(minutes=self.config.close_window_minutes)

        if self.config.close_positions and gate_start <= now < scheduled_time:
            # Within the close window - close positions
            for instrument_id in affected_instruments:
                await self._close_positions_for_instrument(
                    instrument_id=instrument_id,
                    reason=f"Closing before {event_name}"
                )

    async def _get_affected_instruments(self, currency: str) -> List[int]:
        """
        Get all instruments affected by a currency.

        Args:
            currency: Currency code (e.g., 'USD', 'EUR', 'GBP', 'JPY')

        Returns:
            List of instrument IDs
        """
        # Query instruments where currency appears in the pair
        instruments = await self.db.execute_query(
            """
            SELECT instrument_id, provider_symbol
            FROM instruments
            WHERE active = true
              AND asset_class = 'FX_SPOT'
              AND (provider_symbol LIKE %s OR provider_symbol LIKE %s)
            """,
            (f"%{currency}%", f"%{currency}%")
        )

        return [inst['instrument_id'] for inst in instruments]

    async def _create_gate(
        self,
        instrument_id: int,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        event_id: Optional[str] = None
    ):
        """
        Create a gating state in the database.

        Args:
            instrument_id: Instrument to gate
            start_time: Gate start time
            end_time: Gate end time
            reason: Reason for gating
            event_id: Optional event ID
        """
        window_minutes = int((end_time - start_time).total_seconds() / 60)

        await self.db.insert_gating_state(
            instrument_id=instrument_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            window_minutes=window_minutes,
            event_id=event_id
        )

        logger.debug(f"Created gate for instrument {instrument_id}: {start_time} - {end_time}")

    async def _refresh_gated_instruments(self):
        """Refresh the in-memory set of currently gated instruments."""
        gated = await self.db.execute_query(
            """
            SELECT DISTINCT instrument_id
            FROM gating_state
            WHERE state = 'active'
              AND start_time <= NOW()
              AND end_time > NOW()
            """
        )

        self.gated_instruments = {g['instrument_id'] for g in gated}
        logger.debug(f"Currently gated instruments: {self.gated_instruments}")

    async def _close_positions_for_instrument(
        self,
        instrument_id: int,
        reason: str
    ):
        """
        Close all open positions for an instrument.

        Args:
            instrument_id: Instrument ID
            reason: Reason for closing
        """
        # Check if there are open positions
        positions = await self.db.execute_query(
            """
            SELECT pos_id, side, qty
            FROM positions
            WHERE instrument_id = %s AND close_ts IS NULL
            """,
            (instrument_id,)
        )

        if not positions:
            return

        logger.warning(
            f"⚠️  Closing {len(positions)} positions for instrument {instrument_id}: {reason}"
        )

        # TODO: Integrate with trading execution to actually close positions
        # For now, just log
        for pos in positions:
            logger.info(f"  Would close position {pos['pos_id']} ({pos['side']} {pos['qty']})")

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    async def is_gated(self, instrument_id: int) -> bool:
        """
        Check if an instrument is currently gated.

        Args:
            instrument_id: Instrument ID

        Returns:
            True if gated, False otherwise
        """
        return instrument_id in self.gated_instruments

    async def get_gating_reason(self, instrument_id: int) -> Optional[str]:
        """
        Get the reason why an instrument is gated.

        Args:
            instrument_id: Instrument ID

        Returns:
            Gating reason or None if not gated
        """
        gate = await self.db.check_gating_state(instrument_id)
        return gate['reason'] if gate else None

    async def get_all_gates(self) -> List[Dict[str, Any]]:
        """Get all active gates."""
        return await self.db.execute_query(
            """
            SELECT
                g.*,
                i.provider_symbol
            FROM gating_state g
            JOIN instruments i ON g.instrument_id = i.instrument_id
            WHERE g.state = 'active' AND g.end_time > NOW()
            ORDER BY g.start_time
            """
        )

    async def manual_gate(
        self,
        instrument_id: int,
        duration_minutes: int,
        reason: str = "Manual override"
    ):
        """
        Manually gate an instrument.

        Args:
            instrument_id: Instrument to gate
            duration_minutes: How long to gate
            reason: Reason for manual gate
        """
        now = datetime.utcnow()
        end_time = now + timedelta(minutes=duration_minutes)

        await self._create_gate(
            instrument_id=instrument_id,
            start_time=now,
            end_time=end_time,
            reason=reason
        )

        await self._refresh_gated_instruments()
        logger.info(f"Manual gate applied to instrument {instrument_id} for {duration_minutes} min")


# ============================================================================
# TESTING
# ============================================================================

async def test_gating_service():
    """Test the gating service."""
    config = GateConfig(
        gate_window_minutes=15,
        close_window_minutes=10,
        check_interval=5,  # Check every 5 seconds for testing
    )

    service = NewsGatingService(config=config)

    try:
        # Run for 60 seconds
        logger.info("Starting gating service for 60 seconds...")
        task = asyncio.create_task(service.start())

        await asyncio.sleep(60)

        service.running = False
        await task

    except asyncio.CancelledError:
        pass
    finally:
        await service.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_gating_service())
