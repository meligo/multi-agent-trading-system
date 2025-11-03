#!/usr/bin/env python3
"""
Standalone DataHub Server

Starts DataHub on port 50000 and keeps it running.
This must be started BEFORE the WebSocket collector and dashboard.

Usage:
    python start_datahub_server.py
"""

import logging
import signal
import sys
from data_hub import start_data_hub_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global manager reference for cleanup
manager = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    logger.info("\n🛑 Shutting down DataHub server...")
    if manager:
        try:
            manager.shutdown()
        except:
            pass
    sys.exit(0)

def main():
    """Start DataHub server and keep it running."""
    global manager

    print("=" * 80)
    print("🚀 DATAHUB STANDALONE SERVER")
    print("=" * 80)
    print()

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start DataHub manager
        logger.info("Starting DataHub manager on 127.0.0.1:50000...")

        manager = start_data_hub_manager(
            address=('127.0.0.1', 50000),
            authkey=b'forex_scalper_2025'
        )

        # Get DataHub instance
        hub = manager.DataHub()

        logger.info("✅ DataHub manager started successfully!")
        logger.info(f"   Address: 127.0.0.1:50000")
        logger.info(f"   Auth key: forex_scalper_2025")
        logger.info(f"   Status: {hub.get_status()}")
        print()
        logger.info("🟢 DataHub is ready to accept connections")
        logger.info("   Press Ctrl+C to stop")
        print()

        # Keep server running (manager already started serve_forever in background)
        # Just wait indefinitely
        import time
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("\n🛑 Received interrupt signal")
    except Exception as e:
        logger.error(f"❌ Failed to start DataHub: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if manager:
            try:
                logger.info("Shutting down manager...")
                manager.shutdown()
            except:
                pass
        logger.info("👋 DataHub server stopped")

if __name__ == "__main__":
    main()
