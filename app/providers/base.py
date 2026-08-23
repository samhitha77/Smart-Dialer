"""
Base telecom provider interface.

Every concrete provider must implement this interface.
The rest of the system (Call Allocator, Event Processor) depends ONLY on
this abstract base class — never on provider-specific implementations.

This enforces the dependency inversion principle:
  High-level modules (allocator) depend on abstractions (TelecomProvider),
  not on concrete details (ProviderA, ProviderB).
"""

import abc
import dataclasses
import enum


class ProviderCallResult(str, enum.Enum):
    """Result returned by the provider when initiating a call."""
    SUCCESS = "SUCCESS"       # Call accepted; provider will send events
    FAILED = "FAILED"         # Immediate failure (busy network, bad number, etc.)
    TIMEOUT = "TIMEOUT"       # Provider did not respond in time


@dataclasses.dataclass
class InitiateCallResult:
    """
    Result of asking the provider to initiate a call.

    provider_call_id: A unique reference assigned by the provider.
                      Use this to correlate future events to this call.
    result:           Whether the provider accepted the call.
    error_message:    Human-readable reason for failure (if any).
    """
    result: ProviderCallResult
    provider_call_id: str | None = None
    error_message: str | None = None


@dataclasses.dataclass
class ProviderHealthStatus:
    """
    Snapshot of a provider's current health.

    health_score: 0.0 (completely broken) to 1.0 (fully healthy).
    is_healthy:   Convenience boolean; True when health_score >= 0.7.
    """
    health_score: float          # 0.0 – 1.0
    is_healthy: bool
    failure_rate: float          # Recent proportion of failed calls
    avg_latency_ms: float        # Average call setup latency in milliseconds
    details: str = ""            # Human-readable summary


class TelecomProvider(abc.ABC):
    """
    Abstract base class for all telecom providers.

    Concrete providers must implement:
      - initiate_call()
      - get_health()
      - name (property)
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return a human-readable provider name."""

    @abc.abstractmethod
    def initiate_call(self, borrower_phone: str, agent_id: int) -> InitiateCallResult:
        """
        Ask the provider to start an outbound call to borrower_phone.
        Connect the call to the agent identified by agent_id.

        This call is synchronous in the prototype — in production it would
        be asynchronous and events would arrive via webhooks.
        """

    @abc.abstractmethod
    def get_health(self) -> ProviderHealthStatus:
        """
        Return the current health of this provider.
        Used by the Safety Controller and Predictive Pacing Engine.
        """
