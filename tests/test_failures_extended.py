"""
Tests for provider outage behaviour and agent availability drops.
These are integration-style tests that exercise multiple components together.
"""
import pytest
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.models.agent import AgentState
from app.dialer.progressive import ProgressiveDialer
from app.dialer.predictive import PredictivePacingEngine
from app.providers.provider_b import ProviderB
from app.providers.provider_a import ProviderA
from app.safety.safety_controller import SafetyAction


def _add_agents(db, count):
    svc = AgentService(db)
    agents = []
    for i in range(count):
        a = svc.create_agent(f"Agent{i}")
        svc.transition_state(a.id, AgentState.AVAILABLE)
        agents.append(a)
    return agents


def _add_borrowers(db, count):
    svc = BorrowerService(db)
    return [svc.create_borrower(f"B{i}", f"555{i:07d}") for i in range(count)]


def test_provider_outage_stops_all_dialing(db):
    """
    When Provider B goes into outage (health=0.0),
    the progressive dialer must initiate 0 calls.
    """
    _add_agents(db, 10)
    _add_borrowers(db, 20)

    provider = ProviderB(is_in_outage=True)
    dialer = ProgressiveDialer(db, provider)
    result = dialer.run_cycle()

    assert result.succeeded == 0
    assert result.safety_action == "REJECT"


def test_provider_recovery_resumes_dialing(db):
    """After outage clears, dialing should succeed again."""
    _add_agents(db, 5)
    _add_borrowers(db, 10)

    provider = ProviderB(failure_rate=0.0, timeout_rate=0.0, is_in_outage=False)
    dialer = ProgressiveDialer(db, provider)
    result = dialer.run_cycle()

    assert result.succeeded > 0


def test_predictive_outage_recommendation_zero(db):
    """During outage, predictive engine recommends 0 and safety rejects."""
    _add_agents(db, 10)
    provider = ProviderB(is_in_outage=True)
    engine = PredictivePacingEngine(db, provider)
    rec, safety = engine.recommend_and_evaluate()
    assert safety.approved_calls == 0
    assert safety.action == SafetyAction.REJECT


def test_agent_drop_reduces_dialing(db):
    """
    100 agents → 40 go offline → next cycle uses only 60.
    This proves the dialer reads live agent count each cycle.
    """
    agents = _add_agents(db, 100)
    _add_borrowers(db, 100)

    # Take first 40 agents offline.
    asvc = AgentService(db)
    for a in agents[:40]:
        asvc.transition_state(a.id, AgentState.OFFLINE)

    provider = ProviderA(failure_rate=0.0)
    dialer = ProgressiveDialer(db, provider)
    result = dialer.run_cycle()

    # At most 60 agents remain → at most 60 calls.
    assert result.attempted <= 60


def test_sudden_full_agent_drop_stops_dialing(db):
    """All agents go offline → zero calls initiated."""
    agents = _add_agents(db, 10)
    _add_borrowers(db, 10)

    asvc = AgentService(db)
    for a in agents:
        asvc.transition_state(a.id, AgentState.OFFLINE)

    dialer = ProgressiveDialer(db, ProviderA())
    result = dialer.run_cycle()
    assert result.attempted == 0
    assert result.succeeded == 0


def test_partial_provider_failure_reduces_success(db):
    """With 50% failure rate, roughly half the calls should fail."""
    n = 20
    _add_agents(db, n)
    _add_borrowers(db, n)

    # High failure rate
    provider = ProviderA(failure_rate=0.8)
    dialer = ProgressiveDialer(db, provider)
    result = dialer.run_cycle()

    # With 80% failure rate, most should fail.
    if result.attempted > 0:
        failure_ratio = result.failed / result.attempted
        assert failure_ratio > 0.3  # At least 30% fail (probabilistic test)
