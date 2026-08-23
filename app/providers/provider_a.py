"""
Provider A — Fast and reliable mock telecom provider.

Characteristics:
  - Low failure rate (5%)
  - Low latency (10–50 ms)
  - Events arrive in the expected order
  - No duplicate events
  - Health score stays high (0.95 by default)

Think of this as a Tier-1 telecom carrier with an excellent SLA.
"""

import random
import uuid

from app.providers.base import (
    InitiateCallResult,
    ProviderCallResult,
    ProviderHealthStatus,
    TelecomProvider,
)


class ProviderA(TelecomProvider):
    """
    Reliable provider — low failure rate, ordered events.

    Parameters
    ----------
    failure_rate : float
        Probability (0–1) that a call initiation fails immediately.
        Default 0.05 (5%).
    """

    def __init__(self, failure_rate: float = 0.05):
        self._failure_rate = failure_rate
        # Counters for health tracking
        self._total_calls = 0
        self._failed_calls = 0

    @property
    def name(self) -> str:
        return "ProviderA"

    def initiate_call(self, borrower_phone: str, agent_id: int) -> InitiateCallResult:
        """
        Simulate a reliable call initiation.
        Fails with low probability; otherwise returns a unique call ID.
        """
        self._total_calls += 1

        if random.random() < self._failure_rate:
            self._failed_calls += 1
            return InitiateCallResult(
                result=ProviderCallResult.FAILED,
                error_message="Network busy (simulated Provider A failure)",
            )

        # Generate a unique provider-side call ID.
        provider_call_id = f"PA-{uuid.uuid4().hex[:12].upper()}"
        return InitiateCallResult(
            result=ProviderCallResult.SUCCESS,
            provider_call_id=provider_call_id,
        )

    def get_health(self) -> ProviderHealthStatus:
        """Calculate health from actual call statistics."""
        if self._total_calls == 0:
            failure_rate = 0.0
        else:
            failure_rate = self._failed_calls / self._total_calls

        # Health score: 1.0 minus the observed failure rate, clamped to [0, 1].
        health_score = max(0.0, 1.0 - failure_rate)

        return ProviderHealthStatus(
            health_score=health_score,
            is_healthy=health_score >= 0.7,
            failure_rate=failure_rate,
            avg_latency_ms=30.0,  # Fast provider — fixed low latency
            details=f"ProviderA: {self._total_calls} calls, {failure_rate:.1%} failure rate",
        )
