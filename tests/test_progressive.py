"""Tests for the progressive dialer."""
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService
from app.models.agent import AgentState
from app.dialer.progressive import ProgressiveDialer
from app.providers.provider_a import ProviderA


def _add_agents(db, count: int) -> list:
    svc = AgentService(db)
    agents = []
    for i in range(count):
        a = svc.create_agent(f"Agent{i}")
        svc.transition_state(a.id, AgentState.AVAILABLE)
        agents.append(a)
    return agents


def _add_borrowers(db, count: int) -> list:
    svc = BorrowerService(db)
    return [svc.create_borrower(f"Borrower{i}", f"555{i:07d}") for i in range(count)]


def test_progressive_does_not_exceed_available_agents(db):
    """
    Core progressive safety rule:
    calls_initiated ≤ available_agents.
    """
    _add_agents(db, 5)
    _add_borrowers(db, 20)  # More borrowers than agents

    dialer = ProgressiveDialer(db, ProviderA(failure_rate=0.0))
    result = dialer.run_cycle()

    # At most 5 calls (one per agent) should have been attempted.
    assert result.attempted <= 5


def test_progressive_no_agents_no_calls(db):
    """No available agents → zero calls initiated."""
    _add_borrowers(db, 10)
    dialer = ProgressiveDialer(db, ProviderA())
    result = dialer.run_cycle()
    assert result.attempted == 0
    assert result.succeeded == 0


def test_progressive_no_borrowers_no_calls(db):
    """No borrowers in queue → zero calls initiated."""
    _add_agents(db, 5)
    dialer = ProgressiveDialer(db, ProviderA())
    result = dialer.run_cycle()
    assert result.attempted == 0


def test_progressive_uses_safety_controller(db):
    """
    Even progressive dialing goes through the Safety Controller.
    When provider health is critical, no calls should be initiated.
    """
    from app.providers.provider_b import ProviderB
    _add_agents(db, 5)
    _add_borrowers(db, 10)

    # Provider in full outage → health = 0.0.
    provider = ProviderB(is_in_outage=True)
    dialer = ProgressiveDialer(db, provider)
    result = dialer.run_cycle()

    assert result.succeeded == 0
    assert result.safety_action in {"REJECT", "REDUCE"}


def test_progressive_cycle_result_fields(db):
    """ProgressiveDialResult has all expected fields."""
    _add_agents(db, 3)
    _add_borrowers(db, 3)
    dialer = ProgressiveDialer(db, ProviderA(failure_rate=0.0))
    result = dialer.run_cycle()
    assert hasattr(result, "attempted")
    assert hasattr(result, "succeeded")
    assert hasattr(result, "failed")
    assert hasattr(result, "safety_action")


def test_progressive_reliable_provider_succeeds(db):
    """With a perfect provider (0% failure), all calls should succeed."""
    n = 4
    _add_agents(db, n)
    _add_borrowers(db, n)
    dialer = ProgressiveDialer(db, ProviderA(failure_rate=0.0))
    result = dialer.run_cycle()
    # All n calls should succeed.
    assert result.succeeded == n


def test_agents_are_not_double_allocated(db):
    """After a cycle, each agent should be in a non-AVAILABLE state (used)."""
    n = 3
    _add_agents(db, n)
    _add_borrowers(db, n)
    dialer = ProgressiveDialer(db, ProviderA(failure_rate=0.0))
    dialer.run_cycle()

    agent_svc = AgentService(db)
    # All agents should now be DIALING or INITIATED (not AVAILABLE).
    available = agent_svc.count_available_agents()
    assert available == 0, f"Expected 0 available agents after cycle, got {available}."


def test_agent_availability_drop_reduces_calls(db):
    """
    Start with 10 agents, remove 4, next cycle uses only the remaining 6.
    Proves the dialer reacts to live availability.
    """
    agents = _add_agents(db, 10)
    _add_borrowers(db, 20)

    # Remove 4 agents by taking them offline.
    agent_svc = AgentService(db)
    for a in agents[:4]:
        agent_svc.transition_state(a.id, AgentState.OFFLINE)

    dialer = ProgressiveDialer(db, ProviderA(failure_rate=0.0))
    result = dialer.run_cycle()

    # Only 6 agents remain available → at most 6 calls.
    assert result.attempted <= 6
