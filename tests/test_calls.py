"""Tests for call creation and state machine transitions."""
import pytest

from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService, CallStateError
from app.models.agent import AgentState
from app.models.call import CallState


def _make_agent(db, name="Agent"):
    svc = AgentService(db)
    a = svc.create_agent(name)
    svc.transition_state(a.id, AgentState.AVAILABLE)
    svc.atomic_reserve(a.id)
    return a


def _make_borrower(db, name="Borrower"):
    svc = BorrowerService(db)
    b = svc.create_borrower(name, "5550001111")
    svc.atomic_reserve(b.id)
    return b


def test_create_call(db):
    """A new call is created in RESERVED state."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    assert call.state == CallState.RESERVED.value


def test_reserved_to_initiated(db):
    """Valid: RESERVED → INITIATED."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    call = svc.transition_state(call.id, CallState.INITIATED, provider_call_id="PA-TESTCALL")
    assert call.state == CallState.INITIATED.value
    assert call.provider_call_id == "PA-TESTCALL"


def test_initiated_to_ringing(db):
    """Valid: INITIATED → RINGING."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    svc.transition_state(call.id, CallState.INITIATED)
    call = svc.transition_state(call.id, CallState.RINGING)
    assert call.state == CallState.RINGING.value


def test_full_happy_path(db):
    """Full call lifecycle: RESERVED → INITIATED → RINGING → ANSWERED → CONNECTED → COMPLETED."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    for state in [CallState.INITIATED, CallState.RINGING, CallState.ANSWERED,
                  CallState.CONNECTED, CallState.COMPLETED]:
        call = svc.transition_state(call.id, state)
    assert call.state == CallState.COMPLETED.value
    assert call.completed_at is not None


def test_invalid_transition_raises(db):
    """RESERVED → CONNECTED is not valid."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    with pytest.raises(CallStateError):
        svc.transition_state(call.id, CallState.CONNECTED)


def test_terminal_state_no_transition(db):
    """No transitions allowed from COMPLETED."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    for state in [CallState.INITIATED, CallState.RINGING, CallState.ANSWERED,
                  CallState.CONNECTED, CallState.COMPLETED]:
        svc.transition_state(call.id, state)
    with pytest.raises(CallStateError):
        svc.transition_state(call.id, CallState.RINGING)


def test_count_active_calls(db):
    """count_active_calls returns non-terminal calls."""
    a1 = _make_agent(db, "A1")
    a2 = _make_agent(db, "A2")
    b1 = _make_borrower(db, "B1")
    b2 = _make_borrower(db, "B2")
    svc = CallService(db)
    c1 = svc.create_call(a1.id, b1.id)  # active (RESERVED)
    c2 = svc.create_call(a2.id, b2.id)  # will be completed
    for state in [CallState.INITIATED, CallState.RINGING, CallState.ANSWERED,
                  CallState.CONNECTED, CallState.COMPLETED]:
        svc.transition_state(c2.id, state)
    assert svc.count_active_calls() == 1


def test_failed_call_is_terminal(db):
    """A FAILED call cannot be transitioned further."""
    a = _make_agent(db)
    b = _make_borrower(db)
    svc = CallService(db)
    call = svc.create_call(a.id, b.id)
    svc.transition_state(call.id, CallState.FAILED)
    with pytest.raises(CallStateError):
        svc.transition_state(call.id, CallState.INITIATED)
