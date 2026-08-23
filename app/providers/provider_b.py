"""
Provider B — Slow and chaotic mock telecom provider.

Characteristics:
  - Higher failure rate (25%)
  - Occasional timeouts
  - Duplicate events (same event sent twice)
  - Out-of-order events (COMPLETED before ANSWERED, etc.)
  - Variable latency (50–500 ms)

Think of this as a budget VoIP carrier with poor reliability.
The system must handle all of these gracefully:
  - Duplicates → handled by event_id idempotency in event_processor.py
  - Out-of-order → handled by CALL_VALID_TRANSITIONS check in event_processor.py
  - Timeouts / failures → handled by safety controller reducing dialing

Provider B also supports simulated outages to test the outage recovery path.
"""

import random
import uuid

from app.providers.base import (
    InitiateCallResult,
    ProviderCallResult,
    ProviderHealthStatus,
    TelecomProvider,
)


class ProviderB(TelecomProvider):
    """
    Chaotic provider — higher failure rate, timeouts, duplicate/out-of-order events.

    Parameters
    ----------
    failure_rate  : float — probability of immediate call failure (default 0.25)
    timeout_rate  : float — probability of timeout instead of failure (default 0.10)
    is_in_outage  : bool  — when True, all calls fail immediately
    """

    def __init__(
        self,
        failure_rate: float = 0.25,
        timeout_rate: float = 0.10,
        is_in_outage: bool = False,
    ):
        self._failure_rate = failure_rate
        self._timeout_rate = timeout_rate
        self._is_in_outage = is_in_outage
        self._total_calls = 0
        self._failed_calls = 0
        self._timeout_calls = 0

    @property
    def name(self) -> str:
        return "ProviderB"

    def set_outage(self, is_in_outage: bool) -> None:
        """Toggle provider outage mode for testing."""
        self._is_in_outage = is_in_outage

    def initiate_call(self, borrower_phone: str, agent_id: int) -> InitiateCallResult:
        """
        Simulate an unreliable call initiation.
        During an outage, all calls immediately fail.
        Otherwise, fail or timeout at the configured rates.
        """
        self._total_calls += 1

        # During a simulated outage, all calls fail immediately.
        if self._is_in_outage:
            self._failed_calls += 1
            return InitiateCallResult(
                result=ProviderCallResult.FAILED,
                error_message="Provider B is in outage mode",
            )

        roll = random.random()

        if roll < self._timeout_rate:
            # Timeout — provider did not respond.
            self._timeout_calls += 1
            self._failed_calls += 1
            return InitiateCallResult(
                result=ProviderCallResult.TIMEOUT,
                error_message="Provider B timed out (simulated)",
            )

        if roll < self._timeout_rate + self._failure_rate:
            # Outright failure.
            self._failed_calls += 1
            return InitiateCallResult(
                result=ProviderCallResult.FAILED,
                error_message="Provider B rejected call (simulated failure)",
            )

        # Success — return a unique provider call ID.
        provider_call_id = f"PB-{uuid.uuid4().hex[:12].upper()}"
        return InitiateCallResult(
            result=ProviderCallResult.SUCCESS,
            provider_call_id=provider_call_id,
        )

    def get_health(self) -> ProviderHealthStatus:
        """Calculate health from observed failure + timeout statistics."""
        if self._is_in_outage:
            return ProviderHealthStatus(
                health_score=0.0,
                is_healthy=False,
                failure_rate=1.0,
                avg_latency_ms=5000.0,
                details="ProviderB: OUTAGE in progress",
            )

        if self._total_calls == 0:
            failure_rate = 0.0
        else:
            failure_rate = self._failed_calls / self._total_calls

        health_score = max(0.0, 1.0 - failure_rate)

        return ProviderHealthStatus(
            health_score=health_score,
            is_healthy=health_score >= 0.7,
            failure_rate=failure_rate,
            avg_latency_ms=250.0,  # Slow provider
            details=(
                f"ProviderB: {self._total_calls} calls, "
                f"{failure_rate:.1%} failure, "
                f"{self._timeout_calls} timeouts"
            ),
        )

    # ------------------------------------------------------------------
    # Helper: generate chaotic event sequences for simulation
    # ------------------------------------------------------------------

    def generate_events_for_call(self, provider_call_id: str) -> list[dict]:
        """
        Generate the sequence of events this provider would send for a call.
        Sometimes duplicates events; sometimes sends them out of order.

        Used by the simulator — NOT by the real call path.
        """
        normal_sequence = ["RINGING", "ANSWERED", "CONNECTED", "COMPLETED"]
        events = []

        for event_type in normal_sequence:
            event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
            events.append({
                "event_id": event_id,
                "call_id": provider_call_id,
                "event_type": event_type,
            })

            # 20% chance of duplicating this event (same event_id = safe duplicate).
            if random.random() < 0.20:
                events.append({
                    "event_id": event_id,  # Same event_id → will be deduped
                    "call_id": provider_call_id,
                    "event_type": event_type,
                })

        # 15% chance of shuffling the events (out-of-order delivery).
        if random.random() < 0.15:
            random.shuffle(events)

        return events
