"""Tests for failure handling — provider failures, agent crashes, and resource release."""
import pytest
from datetime import datetime, timedelta

from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService
from app.allocation.call_allocator import CallAllocator
from app.models.agent import AgentState
from app.models.borrower import BorrowerState
from app.models.call import CallState
from app.providers.provider_b import ProviderB
from app.providers.provider_a import ProviderA
from datetime import timezone


def _setup_reserved(db):
    """Create an agent, borrower, and call in RESERVED state."""
    asvc = AgentService(db)
    bsvc = BorrowerService(db)
    csvc = CallService(db)

    agent = asvc.create_agent("FailAgent")
    asvc.transition_state(agent.id, AgentState.AVAILABLE)
    asvc.atomic_reserve(agent.id)

    borrower = bsvc.create_borrower("FailBorrower", "5550009999")
    bsvc.atomic_reserve(borrower.id)

    call = csvc.create_call(agent.id, borrower.id)
    return call, agent, borrower


def test_provider_failure_releases_agent(db):
    """When the provider fails a call, the agent is released back to AVAILABLE."""
    call, agent, borrower = _setup_reserved(db)

    # Provider in outage → all calls fail.
    provider = ProviderB(is_in_outage=True)
    allocator = CallAllocator(db, provider)
    b_svc = BorrowerService(db)
    b = b_svc.get_borrower(borrower.id)

    result = allocator.allocate(call, b.phone_number)

    assert result.success is False

    # Agent must be released back to AVAILABLE.
    asvc = AgentService(db)
    updated = asvc.get_agent(agent.id)
    assert updated.state == AgentState.AVAILABLE.value


def test_provider_failure_releases_borrower(db):
    """When the provider fails, the borrower is released back to PENDING."""
    call, agent, borrower = _setup_reserved(db)

    provider = ProviderB(is_in_outage=True)
    allocator = CallAllocator(db, provider)
    b_svc = BorrowerService(db)
    b = b_svc.get_borrower(borrower.id)

    allocator.allocate(call, b.phone_number)

    # Borrower must be PENDING again so it can be re-dialed.
    updated = b_svc.get_borrower(borrower.id)
    assert updated.state == BorrowerState.PENDING.value


def test_provider_failure_marks_call_failed(db):
    """A failed call allocation marks the call as FAILED."""
    call, _, borrower = _setup_reserved(db)
    provider = ProviderB(is_in_outage=True)
    allocator = CallAllocator(db, provider)
    b = BorrowerService(db).get_borrower(borrower.id)
    allocator.allocate(call, b.phone_number)

    csvc = CallService(db)
    updated = csvc.get_call(call.id)
    assert updated.state == CallState.FAILED.value


def test_worker_crash_lease_expiry_releases_agent(db):
    """
    Simulate a worker crash: agent is RESERVED with an old reserved_at timestamp.
    The lease expiry mechanism should release the agent back to AVAILABLE.
    """
    asvc = AgentService(db)
    agent = asvc.create_agent("CrashAgent")
    asvc.transition_state(agent.id, AgentState.AVAILABLE)
    asvc.atomic_reserve(agent.id)

    # Manually backdate the reservation to simulate a crash that happened long ago.
    from app.models.agent import Agent
    db_agent = db.query(Agent).filter(Agent.id == agent.id).first()
    db_agent.reserved_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_agent.reservation_lease_seconds = 60  # Lease is 60s, so this is expired
    db.commit()

    # Run the lease expiry.
    expired = asvc.expire_stale_reservations()
    assert expired == 1

    # Agent should be AVAILABLE again.
    updated = asvc.get_agent(agent.id)
    assert updated.state == AgentState.AVAILABLE.value


def test_worker_crash_lease_expiry_releases_borrower(db):
    """Same crash recovery test for borrowers."""
    bsvc = BorrowerService(db)
    borrower = bsvc.create_borrower("CrashBorrower", "5550008888")
    bsvc.atomic_reserve(borrower.id)

    # Backdate the reservation.
    from app.models.borrower import Borrower
    db_borrower = db.query(Borrower).filter(Borrower.id == borrower.id).first()
    db_borrower.reserved_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_borrower.reservation_lease_seconds = 60
    db.commit()

    expired = bsvc.expire_stale_reservations()
    assert expired == 1

    updated = bsvc.get_borrower(borrower.id)
    assert updated.state == BorrowerState.PENDING.value


def test_valid_reservation_not_expired(db):
    """A fresh reservation should NOT be expired by the lease check."""
    asvc = AgentService(db)
    agent = asvc.create_agent("FreshAgent")
    asvc.transition_state(agent.id, AgentState.AVAILABLE)
    asvc.atomic_reserve(agent.id)

    # Do NOT backdate — reservation is fresh.
    expired = asvc.expire_stale_reservations()
    assert expired == 0

    updated = asvc.get_agent(agent.id)
    assert updated.state == AgentState.RESERVED.value


def test_completed_call_releases_agent_to_wrap_up(db):
    """After a COMPLETED event, agent moves to WRAP_UP."""
    import uuid
    from app.services.event_processor import EventProcessor

    asvc = AgentService(db)
    bsvc = BorrowerService(db)
    csvc = CallService(db)

    agent = asvc.create_agent("WrapAgent")
    asvc.transition_state(agent.id, AgentState.AVAILABLE)
    asvc.atomic_reserve(agent.id)
    asvc.transition_state(agent.id, AgentState.DIALING)

    borrower = bsvc.create_borrower("WrapBorrower", "5550007777")
    bsvc.atomic_reserve(borrower.id)

    call = csvc.create_call(agent.id, borrower.id)
    provider_call_id = "PA-WRAPTEST"
    csvc.transition_state(call.id, CallState.INITIATED, provider_call_id=provider_call_id)

    # Simulate normal event sequence.
    processor = EventProcessor(db)
    for event_type in ["RINGING", "ANSWERED", "CONNECTED"]:
        processor.process(
            event_id=str(uuid.uuid4()),
            provider_call_id=provider_call_id,
            event_type=event_type,
        )

    # After CONNECTED, agent should be CONNECTED.
    updated_agent = asvc.get_agent(agent.id)
    assert updated_agent.state == AgentState.CONNECTED.value

    # Send COMPLETED.
    processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id=provider_call_id,
        event_type="COMPLETED",
    )

    # Agent should now be in WRAP_UP.
    final_agent = asvc.get_agent(agent.id)
    assert final_agent.state == AgentState.WRAP_UP.value
