"""Tests for provider event processing — idempotency and out-of-order handling."""
import uuid

from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService
from app.services.event_processor import EventProcessor
from app.models.agent import AgentState
from app.models.call import CallState


def _setup_call(db, provider_call_id="PA-TEST001"):
    """Helper: create an agent, borrower, and call in INITIATED state."""
    agent_svc = AgentService(db)
    borrower_svc = BorrowerService(db)
    call_svc = CallService(db)

    agent = agent_svc.create_agent("TestAgent")
    agent_svc.transition_state(agent.id, AgentState.AVAILABLE)
    agent_svc.atomic_reserve(agent.id)
    agent_svc.transition_state(agent.id, AgentState.DIALING)

    borrower = borrower_svc.create_borrower("TestBorrower", "5550001234")
    borrower_svc.atomic_reserve(borrower.id)

    call = call_svc.create_call(agent.id, borrower.id)
    call_svc.transition_state(call.id, CallState.INITIATED, provider_call_id=provider_call_id)

    return call, agent, borrower


def test_normal_event_processing(db):
    """A RINGING event moves the call to RINGING state."""
    call, _, _ = _setup_call(db, "PA-NORMAL1")
    processor = EventProcessor(db)
    result = processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id="PA-NORMAL1",
        event_type="RINGING",
    )
    assert result.processed is True
    svc = CallService(db)
    updated_call = svc.get_call(call.id)
    assert updated_call.state == CallState.RINGING.value


def test_duplicate_event_is_ignored(db):
    """The same event_id processed twice — second time is silently ignored."""
    call, _, _ = _setup_call(db, "PA-DUP1")
    processor = EventProcessor(db)
    event_id = str(uuid.uuid4())

    # First processing → should succeed.
    r1 = processor.process(event_id=event_id, provider_call_id="PA-DUP1", event_type="RINGING")
    assert r1.processed is True

    # Second processing with the same event_id → must be ignored.
    r2 = processor.process(event_id=event_id, provider_call_id="PA-DUP1", event_type="RINGING")
    assert r2.processed is False
    assert "Duplicate" in r2.reason or "duplicate" in r2.reason.lower()


def test_multiple_duplicate_events(db):
    """Three copies of the same event — only the first is processed."""
    call, _, _ = _setup_call(db, "PA-DUP2")
    processor = EventProcessor(db)
    event_id = str(uuid.uuid4())

    results = [
        processor.process(event_id=event_id, provider_call_id="PA-DUP2", event_type="RINGING")
        for _ in range(3)
    ]
    assert sum(1 for r in results if r.processed) == 1


def test_out_of_order_event_is_discarded(db):
    """
    COMPLETED arriving before RINGING must be safely discarded.
    The call should stay in INITIATED state.
    """
    call, _, _ = _setup_call(db, "PA-OOO1")
    processor = EventProcessor(db)

    # Send COMPLETED before RINGING — out of order.
    result = processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id="PA-OOO1",
        event_type="COMPLETED",
    )
    assert result.processed is False
    assert "Out-of-order" in result.reason or "not allowed" in result.reason.lower()

    # Call state must be unchanged.
    svc = CallService(db)
    unchanged = svc.get_call(call.id)
    assert unchanged.state == CallState.INITIATED.value


def test_event_for_unknown_call(db):
    """An event for an unknown provider_call_id must be safely discarded."""
    processor = EventProcessor(db)
    result = processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id="PA-DOESNOTEXIST",
        event_type="RINGING",
    )
    assert result.processed is False
    assert result.call_id is None


def test_event_after_terminal_state_discarded(db):
    """Events arriving after COMPLETED are silently discarded."""
    call, _, _ = _setup_call(db, "PA-TERM1")
    svc = CallService(db)

    # Bring call to COMPLETED through all intermediate states.
    for state in [CallState.RINGING, CallState.ANSWERED, CallState.CONNECTED, CallState.COMPLETED]:
        svc.transition_state(call.id, state)

    processor = EventProcessor(db)
    # Try to send another event after call is COMPLETED.
    result = processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id="PA-TERM1",
        event_type="RINGING",
    )
    assert result.processed is False


def test_failed_call_releases_agent(db):
    """When a FAILED event arrives, the agent is released back to AVAILABLE."""
    call, agent, _ = _setup_call(db, "PA-FAIL1")
    processor = EventProcessor(db)

    result = processor.process(
        event_id=str(uuid.uuid4()),
        provider_call_id="PA-FAIL1",
        event_type="FAILED",
    )
    assert result.processed is True

    agent_svc = AgentService(db)
    updated_agent = agent_svc.get_agent(agent.id)
    assert updated_agent.state == AgentState.AVAILABLE.value
