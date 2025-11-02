"""
Database Manager for Multi-Agent Forex Scalping System
Handles PostgreSQL + TimescaleDB connection, setup, and batch writes
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL + TimescaleDB connections and operations.
    Uses async connection pooling for high throughput.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "forex_scalping",
        user: str = "postgres",
        password: str = None,
        min_size: int = 5,
        max_size: int = 20
    ):
        """
        Initialize database manager with connection pool.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_size: Minimum pool size
            max_size: Maximum pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or os.getenv("POSTGRES_PASSWORD", "postgres")

        # Connection string
        self.conn_string = f"host={host} port={port} dbname={database} user={user} password={self.password}"

        # Connection pool (initialized lazily)
        self.pool: Optional[AsyncConnectionPool] = None
        self.min_size = min_size
        self.max_size = max_size

        logger.info(f"DatabaseManager initialized for {database}@{host}:{port}")

    async def initialize(self):
        """Initialize the connection pool."""
        if self.pool is None:
            self.pool = AsyncConnectionPool(
                conninfo=self.conn_string,
                min_size=self.min_size,
                max_size=self.max_size,
                kwargs={"row_factory": dict_row}
            )
            await self.pool.open()
            logger.info(f"Connection pool opened: {self.min_size}-{self.max_size} connections")

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Connection pool closed")

    async def execute_schema(self, schema_file: str = "database_setup.sql"):
        """
        Execute SQL schema file to set up database.

        Args:
            schema_file: Path to SQL file
        """
        schema_path = Path(__file__).parent / schema_file
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        sql = schema_path.read_text()

        # Use a dedicated connection for DDL
        async with await AsyncConnection.connect(self.conn_string) as conn:
            try:
                await conn.execute(sql)
                await conn.commit()
                logger.info(f"✅ Schema executed successfully from {schema_file}")
            except Exception as e:
                logger.error(f"❌ Schema execution failed: {e}")
                raise

    async def batch_insert(
        self,
        table: str,
        columns: List[str],
        rows: List[tuple],
        batch_size: int = 1000
    ):
        """
        Batch insert using COPY for maximum performance.

        Args:
            table: Table name
            columns: List of column names
            rows: List of tuples matching columns
            batch_size: Rows per batch

        Performance: 100k+ rows/sec on modern hardware
        """
        if not rows:
            return

        await self.initialize()

        async with self.pool.connection() as conn:
            async with conn.cursor() as cursor:
                # Use COPY for bulk insert
                async with cursor.copy(
                    f"COPY {table} ({', '.join(columns)}) FROM STDIN"
                ) as copy:
                    for row in rows:
                        await copy.write_row(row)

                await conn.commit()

        logger.debug(f"Inserted {len(rows)} rows into {table}")

    async def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dictionaries
        """
        await self.initialize()

        async with self.pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()

    async def execute_one(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return one result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Single row as dictionary or None
        """
        await self.initialize()

        async with self.pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchone()

    async def execute_command(
        self,
        command: str,
        params: Optional[tuple] = None
    ):
        """
        Execute an INSERT/UPDATE/DELETE command.

        Args:
            command: SQL command
            params: Command parameters
        """
        await self.initialize()

        async with self.pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(command, params)
                await conn.commit()

    # ========================================================================
    # HIGH-LEVEL HELPERS
    # ========================================================================

    async def get_instrument_id(
        self,
        provider: str,
        symbol: str
    ) -> Optional[int]:
        """Get instrument_id for a provider symbol."""
        result = await self.execute_one(
            "SELECT instrument_id FROM instruments WHERE provider = %s AND provider_symbol = %s AND active = true",
            (provider, symbol)
        )
        return result['instrument_id'] if result else None

    async def get_active_instruments(self) -> List[Dict[str, Any]]:
        """Get all active instruments."""
        return await self.execute_query(
            "SELECT * FROM instruments WHERE active = true ORDER BY asset_class, provider_symbol"
        )

    async def get_symbol_mapping(self, mapping_group: str) -> Optional[Dict[str, Any]]:
        """Get spot-futures mapping."""
        return await self.execute_one(
            "SELECT * FROM symbol_mapping WHERE mapping_group = %s",
            (mapping_group,)
        )

    async def check_gating_state(self, instrument_id: int) -> Optional[Dict[str, Any]]:
        """Check if instrument is currently gated."""
        return await self.execute_one(
            """
            SELECT * FROM gating_state
            WHERE instrument_id = %s
              AND state = 'active'
              AND end_time > NOW()
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (instrument_id,)
        )

    async def insert_gating_state(
        self,
        instrument_id: int,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        window_minutes: int,
        event_id: Optional[str] = None
    ):
        """Insert a new gating state."""
        await self.execute_command(
            """
            INSERT INTO gating_state
            (instrument_id, start_time, end_time, reason, window_minutes, state, event_id)
            VALUES (%s, %s, %s, %s, %s, 'active', %s)
            ON CONFLICT (instrument_id, start_time) DO NOTHING
            """,
            (instrument_id, start_time, end_time, reason, window_minutes, event_id)
        )

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return await self.execute_query(
            "SELECT * FROM v_open_positions ORDER BY holding_seconds DESC"
        )

    async def get_latest_alignment(self, mapping_group: str) -> Optional[Dict[str, Any]]:
        """Get latest cross-asset alignment for futures-spot pair."""
        return await self.execute_one(
            """
            SELECT * FROM cross_asset_alignment
            WHERE group_id = %s
            ORDER BY as_of_ts DESC
            LIMIT 1
            """,
            (mapping_group,)
        )


# ============================================================================
# SETUP UTILITIES
# ============================================================================

async def setup_database(
    host: str = "localhost",
    port: int = 5432,
    database: str = "forex_scalping",
    user: str = "postgres",
    password: str = None,
    drop_existing: bool = False
):
    """
    Create database and execute schema.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        drop_existing: If True, drop and recreate database
    """
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")

    # Connect to postgres database to create our database
    admin_conn_string = f"host={host} port={port} dbname=postgres user={user} password={password}"

    async with await AsyncConnection.connect(admin_conn_string, autocommit=True) as conn:
        async with conn.cursor() as cursor:
            # Drop if requested
            if drop_existing:
                logger.warning(f"Dropping database {database}...")
                await cursor.execute(f"DROP DATABASE IF EXISTS {database}")

            # Create database
            logger.info(f"Creating database {database}...")
            try:
                await cursor.execute(f"CREATE DATABASE {database}")
                logger.info(f"✅ Database {database} created")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Database {database} already exists")
                else:
                    raise

    # Execute schema
    db = DatabaseManager(host, port, database, user, password)
    await db.execute_schema()

    logger.info("✅ Database setup complete!")


async def test_connection():
    """Test database connection and schema."""
    db = DatabaseManager()
    await db.initialize()

    try:
        # Test instruments
        instruments = await db.get_active_instruments()
        logger.info(f"Found {len(instruments)} active instruments:")
        for inst in instruments:
            logger.info(f"  - {inst['provider']}/{inst['provider_symbol']} (ID: {inst['instrument_id']})")

        # Test symbol mappings
        mappings = await db.execute_query("SELECT * FROM symbol_mapping")
        logger.info(f"Found {len(mappings)} symbol mappings:")
        for m in mappings:
            logger.info(f"  - {m['futures_symbol']} ↔ {m['spot_symbol']} (lag: {m['correlation_lag_ms']}ms)")

        logger.info("✅ Database connection test passed!")

    finally:
        await db.close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        if len(sys.argv) > 1 and sys.argv[1] == "setup":
            drop = "--drop" in sys.argv
            await setup_database(drop_existing=drop)
        elif len(sys.argv) > 1 and sys.argv[1] == "test":
            await test_connection()
        else:
            print("Usage:")
            print("  python database_manager.py setup [--drop]  # Create database and schema")
            print("  python database_manager.py test           # Test connection")

    asyncio.run(main())
