"""Tests for Provider A and Provider B mock providers."""
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.providers.base import ProviderCallResult


def test_provider_a_success():
    """ProviderA with 0% failure rate should always succeed."""
    provider = ProviderA(failure_rate=0.0)
    result = provider.initiate_call("5550001111", agent_id=1)
    assert result.result == ProviderCallResult.SUCCESS
    assert result.provider_call_id is not None
    assert result.provider_call_id.startswith("PA-")


def test_provider_a_always_fails_when_rate_is_1():
    """ProviderA with 100% failure rate always fails."""
    provider = ProviderA(failure_rate=1.0)
    result = provider.initiate_call("5550001111", agent_id=1)
    assert result.result == ProviderCallResult.FAILED


def test_provider_a_health_is_high():
    """Fresh ProviderA has high health score."""
    provider = ProviderA(failure_rate=0.05)
    health = provider.get_health()
    assert health.health_score >= 0.7
    assert health.is_healthy is True


def test_provider_b_outage_fails_all():
    """ProviderB in outage mode fails every call."""
    provider = ProviderB(is_in_outage=True)
    for _ in range(5):
        result = provider.initiate_call("5550002222", agent_id=2)
        assert result.result == ProviderCallResult.FAILED


def test_provider_b_health_is_zero_during_outage():
    """ProviderB outage → health_score = 0.0."""
    provider = ProviderB(is_in_outage=True)
    health = provider.get_health()
    assert health.health_score == 0.0
    assert health.is_healthy is False


def test_provider_b_recovery_after_outage():
    """After clearing the outage flag, ProviderB can succeed again."""
    provider = ProviderB(failure_rate=0.0, timeout_rate=0.0, is_in_outage=True)
    provider.set_outage(False)
    result = provider.initiate_call("5550003333", agent_id=3)
    assert result.result == ProviderCallResult.SUCCESS


def test_provider_b_generates_chaotic_events():
    """ProviderB generates events with possible duplicates/shuffle."""
    provider = ProviderB()
    events = provider.generate_events_for_call("PB-TEST001")
    # Must have at least the 4 normal event types.
    event_types = {e["event_type"] for e in events}
    expected = {"RINGING", "ANSWERED", "CONNECTED", "COMPLETED"}
    assert expected.issubset(event_types)


def test_provider_a_unique_call_ids():
    """Each successful call gets a unique provider_call_id."""
    provider = ProviderA(failure_rate=0.0)
    ids = {provider.initiate_call("555", agent_id=1).provider_call_id for _ in range(20)}
    assert len(ids) == 20, "All provider_call_ids must be unique."


def test_provider_b_health_tracking():
    """ProviderB tracks failures and reflects them in health score."""
    provider = ProviderB(failure_rate=1.0, timeout_rate=0.0)
    for _ in range(10):
        provider.initiate_call("555", agent_id=1)
    health = provider.get_health()
    assert health.failure_rate == 1.0
    assert health.health_score == 0.0
