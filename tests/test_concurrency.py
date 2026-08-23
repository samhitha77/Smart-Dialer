"""
CRITICAL TEST: Concurrency-safe reservation.

These tests prove that:
  1. Two workers cannot reserve the same agent simultaneously.
  2. Two workers cannot reserve the same borrower simultaneously.

How it works:
  - We spin up N threads, each trying to reserve the same resource.
  - We collect who succeeded and who failed.
  - Exactly 1 thread must succeed; all others must fail.

This works because the atomic UPDATE WHERE state='AVAILABLE' ensures that
only the first write wins.  SQLite's WAL mode serialises concurrent writes
to the same row.
"""

import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import agent, borrower, call, provider_event  # noqa: F401
from app.models.agent import AgentState
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService


from sqlalchemy.pool import StaticPool


def _make_session_factory():
    """Create a fresh in-memory database with its own session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine), engine


def test_concurrent_agent_reservation():
    """
    Ten threads race to reserve the same agent.
    Exactly ONE must succeed; the rest must fail (return False).

    This is the most important test in the project.
    """
    Session, engine = _make_session_factory()

    # Create and set up the agent using the setup session.
    setup_db = Session()
    svc = AgentService(setup_db)
    agent_obj = svc.create_agent("Shared Agent")
    svc.transition_state(agent_obj.id, AgentState.AVAILABLE)
    setup_db.close()

    agent_id = agent_obj.id
    num_workers = 10
    results = []
    lock = threading.Lock()

    def try_reserve():
        """Each worker gets its own DB session to simulate a separate process."""
        worker_db = Session()
        worker_svc = AgentService(worker_db)
        success = worker_svc.atomic_reserve(agent_id)
        with lock:
            results.append(success)
        worker_db.close()

    threads = [threading.Thread(target=try_reserve) for _ in range(num_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)

    assert successes == 1, (
        f"Expected exactly 1 successful reservation, got {successes}. "
        f"Results: {results}"
    )
    assert failures == num_workers - 1, (
        f"Expected {num_workers - 1} failures, got {failures}."
    )

    engine.dispose()


def test_concurrent_borrower_reservation():
    """
    Ten threads race to reserve the same borrower.
    Exactly ONE must succeed.
    """
    Session, engine = _make_session_factory()

    setup_db = Session()
    svc = BorrowerService(setup_db)
    borrower_obj = svc.create_borrower("Shared Borrower", "5550001234")
    setup_db.close()

    borrower_id = borrower_obj.id
    num_workers = 10
    results = []
    lock = threading.Lock()

    def try_reserve():
        worker_db = Session()
        worker_svc = BorrowerService(worker_db)
        success = worker_svc.atomic_reserve(borrower_id)
        with lock:
            results.append(success)
        worker_db.close()

    threads = [threading.Thread(target=try_reserve) for _ in range(num_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(1 for r in results if r is True)
    assert successes == 1, (
        f"Expected exactly 1 borrower reservation to succeed, got {successes}. "
        f"Results: {results}"
    )

    engine.dispose()


def test_concurrent_reservation_with_20_threads():
    """
    Stress test: 20 threads compete for 1 agent.
    Still exactly 1 winner.
    """
    Session, engine = _make_session_factory()

    setup_db = Session()
    svc = AgentService(setup_db)
    a = svc.create_agent("Stress Agent")
    svc.transition_state(a.id, AgentState.AVAILABLE)
    setup_db.close()

    agent_id = a.id
    results = []
    lock = threading.Lock()

    def try_reserve():
        worker_db = Session()
        success = AgentService(worker_db).atomic_reserve(agent_id)
        with lock:
            results.append(success)
        worker_db.close()

    threads = [threading.Thread(target=try_reserve) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(results) == 1, f"Expected 1 winner from 20 threads, got {sum(results)}."

    engine.dispose()
