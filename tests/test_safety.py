"""Tests for the Safety Controller."""
import pytest

from app.safety.safety_controller import (
    SafetyController,
    SafetyAction,
    SystemSnapshot,
)
from app.providers.base import ProviderHealthStatus


def _healthy_provider(score: float = 0.95) -> ProviderHealthStatus:
    return ProviderHealthStatus(
        health_score=score,
        is_healthy=score >= 0.7,
        failure_rate=1.0 - score,
        avg_latency_ms=30.0,
    )


def _snapshot(
    available=10,
    ringing=0,
    connected=0,
    reserved=0,
    answer_rate=0.5,
    provider_health_score=0.95,
    total_active=0,
) -> SystemSnapshot:
    return SystemSnapshot(
        available_agents=available,
        ringing_calls=ringing,
        connected_calls=connected,
        reserved_calls=reserved,
        answer_rate=answer_rate,
        provider_health=_healthy_provider(provider_health_score),
        total_active_calls=total_active,
    )


def test_approve_safe_request():
    """Safety Controller approves when request is within safe limits."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(requested_calls=5, snapshot=_snapshot(available=10))
    assert decision.action == SafetyAction.APPROVE
    assert decision.approved_calls == 5


def test_reduce_over_capacity_request():
    """Safety Controller reduces a request that exceeds agent capacity."""
    ctrl = SafetyController()
    # Only 5 agents available, requesting 20 calls.
    decision = ctrl.evaluate(requested_calls=20, snapshot=_snapshot(available=5))
    assert decision.action in {SafetyAction.REDUCE, SafetyAction.REJECT}
    assert decision.approved_calls <= 5


def test_reject_critical_provider_failure():
    """Safety Controller rejects ALL calls when provider health is critically low."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(
        requested_calls=10,
        snapshot=_snapshot(provider_health_score=0.10),
    )
    assert decision.action == SafetyAction.REJECT
    assert decision.approved_calls == 0


def test_fallback_to_progressive_on_low_answer_rate():
    """Very low answer rate triggers FALLBACK_TO_PROGRESSIVE."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(
        requested_calls=15,
        snapshot=_snapshot(available=10, answer_rate=0.01),
    )
    assert decision.action in {SafetyAction.FALLBACK_TO_PROGRESSIVE, SafetyAction.REJECT}


def test_hard_cap_rejected():
    """Requests when active calls exceed ABSOLUTE_MAX_IN_FLIGHT are rejected."""
    from app.safety.safety_controller import ABSOLUTE_MAX_IN_FLIGHT
    ctrl = SafetyController()
    decision = ctrl.evaluate(
        requested_calls=1,
        snapshot=_snapshot(available=50, total_active=ABSOLUTE_MAX_IN_FLIGHT),
    )
    assert decision.action == SafetyAction.REJECT
    assert decision.approved_calls == 0


def test_provider_health_dampens_approval():
    """Provider health of 0.5 reduces approved calls to ~50% of candidate."""
    ctrl = SafetyController()
    # 10 available agents, all free, requesting 10, health = 0.5.
    decision = ctrl.evaluate(
        requested_calls=10,
        snapshot=_snapshot(available=10, provider_health_score=0.5),
    )
    # Should be reduced due to health dampening.
    assert decision.approved_calls < 10
    assert decision.action in {SafetyAction.REDUCE, SafetyAction.REJECT}


def test_zero_available_agents_rejected():
    """No available agents → 0 calls approved."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(
        requested_calls=5,
        snapshot=_snapshot(available=0),
    )
    assert decision.approved_calls == 0


def test_safety_decision_reason_is_populated():
    """Every decision includes a human-readable reason string."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(requested_calls=5, snapshot=_snapshot())
    assert len(decision.reason) > 10, "Reason string should be descriptive."


def test_approved_never_exceeds_requested():
    """Approved count is always ≤ requested count."""
    ctrl = SafetyController()
    decision = ctrl.evaluate(requested_calls=3, snapshot=_snapshot(available=100))
    assert decision.approved_calls <= 3


def test_safety_controller_has_no_provider_import():
    """
    Architectural test: the safety_controller module must not import
    any provider module.  This enforces the bypass-prevention guarantee.
    """
    import importlib
    import sys

    # Remove cached module to force re-inspection
    module_name = "app.safety.safety_controller"
    if module_name in sys.modules:
        mod = sys.modules[module_name]
    else:
        mod = importlib.import_module(module_name)

    source_file = mod.__file__
    with open(source_file) as f:
        source = f.read()

    # The safety controller must NOT import provider_a or provider_b directly.
    assert "from app.providers.provider_a" not in source, \
        "Safety controller must not import ProviderA directly."
    assert "from app.providers.provider_b" not in source, \
        "Safety controller must not import ProviderB directly."
    assert "initiate_call" not in source, \
        "Safety controller must not call initiate_call."
