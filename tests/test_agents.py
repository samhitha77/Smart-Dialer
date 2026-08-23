"""Tests for agent creation and state machine transitions."""
import pytest

from app.services.agent_service import AgentService, AgentStateError
from app.models.agent import AgentState


def test_create_agent(db):
    """A newly created agent starts in OFFLINE state."""
    svc = AgentService(db)
    agent = svc.create_agent("Alice")
    assert agent.id is not None
    assert agent.state == AgentState.OFFLINE.value


def test_offline_to_available(db):
    """Valid transition: OFFLINE → AVAILABLE."""
    svc = AgentService(db)
    agent = svc.create_agent("Alice")
    agent = svc.transition_state(agent.id, AgentState.AVAILABLE)
    assert agent.state == AgentState.AVAILABLE.value


def test_available_to_reserved(db):
    """Valid transition: AVAILABLE → RESERVED."""
    svc = AgentService(db)
    agent = svc.create_agent("Bob")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    agent = svc.transition_state(agent.id, AgentState.RESERVED)
    assert agent.state == AgentState.RESERVED.value


def test_reserved_to_dialing(db):
    """Valid: RESERVED → DIALING."""
    svc = AgentService(db)
    agent = svc.create_agent("Carol")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    svc.transition_state(agent.id, AgentState.RESERVED)
    agent = svc.transition_state(agent.id, AgentState.DIALING)
    assert agent.state == AgentState.DIALING.value


def test_dialing_to_connected(db):
    """Valid: DIALING → CONNECTED."""
    svc = AgentService(db)
    agent = svc.create_agent("Dave")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    svc.transition_state(agent.id, AgentState.RESERVED)
    svc.transition_state(agent.id, AgentState.DIALING)
    agent = svc.transition_state(agent.id, AgentState.CONNECTED)
    assert agent.state == AgentState.CONNECTED.value


def test_connected_to_wrap_up(db):
    """Valid: CONNECTED → WRAP_UP."""
    svc = AgentService(db)
    agent = svc.create_agent("Eve")
    for state in [AgentState.AVAILABLE, AgentState.RESERVED, AgentState.DIALING, AgentState.CONNECTED]:
        svc.transition_state(agent.id, state)
    agent = svc.transition_state(agent.id, AgentState.WRAP_UP)
    assert agent.state == AgentState.WRAP_UP.value


def test_wrap_up_to_available(db):
    """Valid: WRAP_UP → AVAILABLE (agent is ready for next call)."""
    svc = AgentService(db)
    agent = svc.create_agent("Frank")
    for state in [
        AgentState.AVAILABLE, AgentState.RESERVED, AgentState.DIALING,
        AgentState.CONNECTED, AgentState.WRAP_UP
    ]:
        svc.transition_state(agent.id, state)
    agent = svc.transition_state(agent.id, AgentState.AVAILABLE)
    assert agent.state == AgentState.AVAILABLE.value


def test_invalid_transition_raises(db):
    """OFFLINE → CONNECTED must raise AgentStateError."""
    svc = AgentService(db)
    agent = svc.create_agent("Grace")
    with pytest.raises(AgentStateError):
        svc.transition_state(agent.id, AgentState.CONNECTED)


def test_available_to_connected_invalid(db):
    """AVAILABLE → CONNECTED must raise (must go through RESERVED → DIALING first)."""
    svc = AgentService(db)
    agent = svc.create_agent("Hank")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    with pytest.raises(AgentStateError):
        svc.transition_state(agent.id, AgentState.CONNECTED)


def test_available_to_paused_and_back(db):
    """Agents can pause and resume."""
    svc = AgentService(db)
    agent = svc.create_agent("Iris")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    agent = svc.transition_state(agent.id, AgentState.PAUSED)
    assert agent.state == AgentState.PAUSED.value
    agent = svc.transition_state(agent.id, AgentState.AVAILABLE)
    assert agent.state == AgentState.AVAILABLE.value


def test_count_available_agents(db):
    """count_available_agents returns only AVAILABLE agents."""
    svc = AgentService(db)
    a1 = svc.create_agent("Agent1")
    a2 = svc.create_agent("Agent2")
    a3 = svc.create_agent("Agent3")
    svc.transition_state(a1.id, AgentState.AVAILABLE)
    svc.transition_state(a2.id, AgentState.AVAILABLE)
    # a3 stays OFFLINE
    assert svc.count_available_agents() == 2


def test_release_reserved_agent(db):
    """Releasing a reserved agent sets it back to AVAILABLE."""
    svc = AgentService(db)
    agent = svc.create_agent("Jack")
    svc.transition_state(agent.id, AgentState.AVAILABLE)
    svc.atomic_reserve(agent.id)
    svc.release_agent(agent.id)
    refreshed = svc.get_agent(agent.id)
    assert refreshed.state == AgentState.AVAILABLE.value
