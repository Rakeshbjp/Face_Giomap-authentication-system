"""
Database configuration and connection management.
Uses Motor (async MongoDB driver) for non-blocking operations.
"""

import logging
from typing import Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class MongoDB:
    """MongoDB connection manager using Motor async driver."""

    client: Optional[Any] = None
    database: Optional[Any] = None

    @classmethod
    async def connect(cls):
        """Establish connection to MongoDB."""
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=50,
                minPoolSize=10,
                serverSelectionTimeoutMS=5000,
            )
            cls.database = cls.client[settings.MONGODB_DB_NAME]
            # Verify connection
            await cls.client.admin.command("ping")
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")

    @classmethod
    def get_database(cls) -> Any:
        """Get database instance."""
        if cls.database is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return cls.database

    @classmethod
    async def create_indexes(cls):
        """Create required database indexes for performance and uniqueness."""
        db = cls.get_database()
        users_collection = db["users"]

        # Unique indexes on email and phone
        await users_collection.create_index("email", unique=True)
        await users_collection.create_index("phone", unique=True)
        # Index on created_at for sorting
        await users_collection.create_index("created_at")

        logger.info("Database indexes created successfully")


async def get_database() -> Any:
    """Dependency injection for database access."""
    return MongoDB.get_database()
