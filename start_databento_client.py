#!/usr/bin/env python3
"""
Start DataBento Client

Streams CME futures data (6E, 6B, 6J) and generates 1-minute OHLCV candles
with real volume. Pushes candles and order flow metrics to DataHub.
"""

import asyncio
import logging
import signal
import sys
from databento_client import DataBentoClient
from data_hub import connect_to_data_hub

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global client reference for cleanup
client = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    if client:
        client.running = False
    sys.exit(0)


async def main():
    """Start DataBento client."""
    global client

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connect to DataHub
    logger.info("Connecting to DataHub...")
    try:
        data_hub = connect_to_data_hub(('127.0.0.1', 50000), b'forex_scalper_2025')
        logger.info("✅ Connected to DataHub")
    except Exception as e:
        logger.error(f"❌ Failed to connect to DataHub: {e}")
        logger.error("Make sure DataHub server is running: python start_datahub_server.py")
        return

    # Create DataBento client
    logger.info("Initializing DataBento client...")
    client = DataBentoClient(data_hub=data_hub)

    logger.info("=" * 80)
    logger.info("DATABENTO CLIENT STARTING")
    logger.info("=" * 80)
    logger.info("Dataset: GLBX.MDP3 (CME Globex)")
    logger.info("Schema: mbp-10 (Market By Price)")
    logger.info("Symbols: 6E (EUR), 6B (GBP), 6J (JPY)")
    logger.info("")
    logger.info("Generating:")
    logger.info("  • 1-minute OHLCV candles (real volume from trades)")
    logger.info("  • Order flow metrics (OFI, volume delta, VPIN)")
    logger.info("")
    logger.info("Pushing to DataHub on port 50000")
    logger.info("=" * 80)

    # Start streaming
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Error during streaming: {e}", exc_info=True)
    finally:
        logger.info("Shutting down DataBento client...")
        await client.stop()

        # Print stats
        logger.info("=" * 80)
        logger.info("DATABENTO CLIENT STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Messages received: {client.messages_received}")
        logger.info(f"Messages processed: {client.messages_processed}")
        logger.info(f"Candles generated: {client.candles_generated}")
        logger.info(f"Order flow updates: {client.order_flow_updates}")
        logger.info(f"Sequence gaps: {client.sequence_gaps}")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
