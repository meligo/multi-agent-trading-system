#!/usr/bin/env python3
"""
Emergency Database Setup Script
Loads the schema into forexscalper_dev database
"""

import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

from database_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_database():
    """Load schema into database."""

    logger.info("=" * 70)
    logger.info("DATABASE SETUP - Loading Schema")
    logger.info("=" * 70)

    # Initialize database manager
    db = DatabaseManager()

    try:
        # Connect
        logger.info("Connecting to database...")
        await db.initialize()
        logger.info(f"✅ Connected to: {db.database}@{db.host}:{db.port}")

        # Check if tables already exist
        logger.info("\nChecking for existing tables...")
        result = await db.execute_query(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )

        if result:
            logger.warning(f"Found {len(result)} existing tables:")
            for row in result:
                logger.warning(f"  - {row['tablename']}")

            response = input("\n⚠️  Tables exist. Drop and recreate? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Aborted by user.")
                return

            logger.info("Dropping existing tables...")
            await db.execute_command("DROP SCHEMA public CASCADE")
            await db.execute_command("CREATE SCHEMA public")
            await db.execute_command("GRANT ALL ON SCHEMA public TO postgres")
            await db.execute_command("GRANT ALL ON SCHEMA public TO public")
            logger.info("✅ Schema reset complete")
        else:
            logger.info("✅ No existing tables found")

        # Load schema
        logger.info("\nLoading schema from database_setup_clean.sql...")
        await db.execute_schema('database_setup_clean.sql')
        logger.info("✅ Schema loaded successfully!")

        # Verify tables
        logger.info("\nVerifying tables...")
        result = await db.execute_query(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )

        logger.info(f"✅ Created {len(result)} tables:")
        for row in result:
            logger.info(f"  - {row['tablename']}")

        # Check instruments
        logger.info("\nVerifying seed data...")
        instruments = await db.execute_query("SELECT * FROM instruments ORDER BY instrument_id")
        logger.info(f"✅ Found {len(instruments)} instruments:")
        for inst in instruments:
            logger.info(f"  - {inst['provider']}/{inst['provider_symbol']} (ID: {inst['instrument_id']})")

        # Check symbol mappings
        mappings = await db.execute_query("SELECT * FROM symbol_mapping")
        logger.info(f"✅ Found {len(mappings)} symbol mappings:")
        for m in mappings:
            logger.info(f"  - {m['futures_symbol']} ↔ {m['spot_symbol']} (lag: {m['correlation_lag_ms']}ms)")

        logger.info("\n" + "=" * 70)
        logger.info("✅ DATABASE SETUP COMPLETE!")
        logger.info("=" * 70)
        logger.info("\nYou can now run: streamlit run scalping_dashboard.py")

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        raise

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(setup_database())
