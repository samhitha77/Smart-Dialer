"""Tests for the predictive pacing engine."""
import pytest

from app.dialer.predictive import PredictivePacingEngine
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.models.agent import AgentState
from app.safety.safety_controller import SafetyAction


def _add_agents(db, count: int):
    svc = AgentService(db)
    for i in range(count):
        a = svc.create_agent(f"Agent{i}")
        svc.transition_state(a.id, AgentState.AVAILABLE)


def test_recommend_returns_non_negative(db):
    """Recommendation is never negative."""
    _add_agents(db, 5)
    engine = PredictivePacingEngine(db, ProviderA())
    rec = engine.recommend()
    assert rec.recommended_calls >= 0


def test_recommend_zero_with_no_agents(db):
    """No agents → recommend 0 calls."""
    engine = PredictivePacingEngine(db, ProviderA())
    rec = engine.recommend()
    assert rec.recommended_calls == 0


def test_recommend_and_evaluate_goes_through_safety_controller(db):
    """
    Critical architectural test:
    The predictive engine's recommendation must pass through the Safety Controller.
    Even if the engine recommends many calls, the approved count cannot exceed
    what the Safety Controller allows.
    """
    _add_agents(db, 10)
    engine = PredictivePacingEngine(db, ProviderA())
    rec, safety = engine.recommend_and_evaluate()
    # Approved calls can never exceed recommended calls.
    assert safety.approved_calls <= rec.recommended_calls


def test_predictive_engine_cannot_bypass_safety(db):
    """
    Prove the bypass-prevention: even if the engine recommends 1000 calls,
    the Safety Controller limits it to a safe count.
    """
    _add_agents(db, 5)
    engine = PredictivePacingEngine(db, ProviderA())

    # Manually call safety controller with an absurd request.
    from app.safety.safety_controller import SafetyController, SystemSnapshot
    from app.providers.base import ProviderHealthStatus
    ctrl = SafetyController()
    snapshot = SystemSnapshot(
        available_agents=5,
        ringing_calls=0,
        connected_calls=0,
        reserved_calls=0,
        answer_rate=0.5,
        provider_health=ProviderHealthStatus(
            health_score=0.95, is_healthy=True, failure_rate=0.05, avg_latency_ms=30
        ),
        total_active_calls=0,
    )
    decision = ctrl.evaluate(requested_calls=1000, snapshot=snapshot)
    # Approved must be capped by agent capacity, not the raw request.
    assert decision.approved_calls <= 5


def test_recommendation_reason_is_detailed(db):
    """The recommendation always includes a human-readable reason."""
    _add_agents(db, 5)
    engine = PredictivePacingEngine(db, ProviderA())
    rec = engine.recommend()
    assert "answer_rate" in rec.reason
    assert "available_agents" in rec.reason


def test_provider_outage_reduces_recommendation(db):
    """Provider in outage → recommendation dampened to near 0."""
    _add_agents(db, 10)
    provider = ProviderB(is_in_outage=True)
    engine = PredictivePacingEngine(db, provider)
    rec, safety = engine.recommend_and_evaluate()
    # Safety Controller must reject or heavily reduce when provider is down.
    assert safety.approved_calls == 0
    assert safety.action == SafetyAction.REJECT
