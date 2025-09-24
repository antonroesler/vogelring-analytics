"""
Database connection and session management
"""

# WIP: THIS IS NOT YET WORKING
# THIS CAN BE FULLY CHANGED

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://vogelring:devpassword123@localhost:5432/vogelring")

# Create SQLAlchemy engine with optimized settings for Raspberry Pi
engine = create_engine(
    DATABASE_URL,
    # Connection pool settings optimized for Raspberry Pi resources
    poolclass=QueuePool,
    pool_size=3,  # Reduced pool size for Raspberry Pi memory constraints
    max_overflow=7,  # Lower overflow for resource management
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=1800,  # Recycle connections every 30 minutes (more frequent)
    pool_timeout=30,  # Connection timeout for better resource management
    # Performance optimizations
    connect_args={
        "application_name": "vogelring_backend",
        # PostgreSQL-specific optimizations for Raspberry Pi
        "connect_timeout": 10,
    },
    # Query optimization settings
    execution_options={
        "isolation_level": "READ_COMMITTED",
        "autocommit": False,
    },
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",  # Enable SQL logging if needed
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Event listeners for connection management
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set database connection parameters if needed"""
    pass


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log connection checkout for debugging"""
    logger.debug("Connection checked out from pool")


@contextmanager
def get_db_session():
    """
    Context manager for database sessions (for use outside FastAPI)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_performance_indexes():
    """
    Create performance indexes for optimized queries
    """
    try:
        with engine.connect() as conn:
            # Call the PostgreSQL function to create performance indexes
            conn.execute(text("SELECT create_performance_indexes();"))
            conn.commit()
        logger.info("Performance indexes created successfully")
    except Exception as e:
        logger.warning(f"Error creating performance indexes (may already exist): {e}")
        # Don't raise here as indexes might already exist


def check_connection():
    """
    Check database connection health
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
