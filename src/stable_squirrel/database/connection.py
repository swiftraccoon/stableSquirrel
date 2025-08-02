"""Database connection management with asyncpg."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, Optional

import asyncpg

from stable_squirrel.config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages TimescaleDB connections using asyncpg for high performance."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            logger.info(f"Connecting to TimescaleDB at {self.config.host}:{self.config.port}")

            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                min_size=self.config.min_pool_size,
                max_size=self.config.max_pool_size,
                command_timeout=60,
            )

            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Connected to: {version}")

                # Check TimescaleDB extension
                if self.config.enable_timescale:
                    try:
                        ts_version = await conn.fetchval(
                            "SELECT extversion FROM pg_extension " "WHERE extname = 'timescaledb'"
                        )
                        if ts_version:
                            logger.info(f"TimescaleDB version: {ts_version}")
                        else:
                            logger.warning(
                                "TimescaleDB extension not found - install with: " "CREATE EXTENSION timescaledb;"
                            )
                    except Exception as e:
                        logger.warning(f"Could not check TimescaleDB version: {e}")

            logger.info("Database connection pool initialized")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get database connection pool."""
        if not self._pool:
            raise RuntimeError("Database not initialized - call initialize() first")
        return self._pool

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return status."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Fetch multiple rows."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        """Fetch single row."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch single value."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @asynccontextmanager
    async def transaction(self) -> AsyncContextManager[asyncpg.Connection]:
        """Get a database connection with transaction management."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute_transaction(self, operations: list[tuple[str, tuple]]) -> list[Any]:
        """Execute multiple operations in a single transaction."""
        async with self.transaction() as conn:
            results = []
            for query, args in operations:
                result = await conn.execute(query, *args)
                results.append(result)
            return results

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            await self.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def get_pool_stats(self) -> dict:
        """Get connection pool statistics."""
        if not self._pool:
            return {"status": "not_initialized"}

        return {
            "status": "active",
            "size": self._pool.get_size(),
            "max_size": self._pool.get_max_size(),
            "min_size": self._pool.get_min_size(),
            "idle_connections": self._pool.get_idle_size(),
        }
