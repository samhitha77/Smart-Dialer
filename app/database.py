"""
SmartDialer — Database setup.

Uses SQLite with SQLAlchemy.  A single engine is created for the whole
application and shared via a session factory.

Why SQLite?
  - Zero configuration.
  - Supports the atomic UPDATE … WHERE rowcount trick we use for
    concurrency-safe agent/borrower reservation.
  - Sufficient for a prototype with hundreds of concurrent agents.
  - See docs/architecture_decision.md for the full rationale.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite file stored in the project root when running normally.
# Tests override DATABASE_URL to use an in-memory database.
DATABASE_URL = "sqlite:///./smartdialer.db"

# check_same_thread=False is required for SQLite when multiple threads
# share the same connection.  SQLAlchemy manages connection pooling safely.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # Set to True to see all SQL statements (useful for debugging)
)

# SessionLocal is a factory: call SessionLocal() to get a new DB session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that yields a DB session and ensures it is closed
    after the request finishes, even if an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they do not already exist."""
    # Import models so SQLAlchemy registers them before create_all.
    from app.models import agent, borrower, call, provider_event  # noqa: F401
    Base.metadata.create_all(bind=engine)
