"""
Shared pytest fixtures.

All tests use an in-memory SQLite database so they are:
  - Fast (no disk I/O)
  - Isolated (each test function gets a fresh DB)
  - Independent of any running server
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
# Import all models to register them with Base before create_all.
from app.models import agent, borrower, call, provider_event  # noqa: F401


@pytest.fixture
def db():
    """
    Provide a fresh in-memory SQLite database session for each test.
    The database is destroyed after the test completes.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
