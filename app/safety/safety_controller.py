"""
Safety Controller — the final authority on how many calls may be initiated.

Architecture principle:
  The pacing engine (progressive or predictive) RECOMMENDS a call count.
  The Safety Controller DECIDES the actual number.
  The Call Allocator EXECUTES that decision.

The pacing engine has NO reference to the provider or the allocator.
The ONLY path to the provider is:
  Pacing Engine → Safety Controller → Call Allocator → Provider

Decision flow
─────────────
  1. HARD REJECT if provider health is critically low (< 0.2 score).
  2. HARD REJECT if the system has more outstanding calls than the hard cap.
  3. FALLBACK TO PROGRESSIVE if the answer rate has fallen below the minimum
     threshold (predictive pacing becomes unreliable at very low answer rates).
  4. Compute max_safe:
       max_safe = available_agents - ringing_calls - connected_calls
     Ringing and connected calls already occupy agent capacity.
  5. Apply answer-rate guard:
       If answer_rate is low, we don't want too many unanswered calls in flight.
       Guard = floor(available_agents * MAX_UNANSWERED_RATIO)
  6. Apply provider health dampener:
       approved = floor(candidate * provider_health_score)
  7. Return min(requested, max_safe, answer_rate_guard, provider_dampened).

Constants are named, documented, and justified — no magic numbers.
"""

import enum
import logging
import math
from dataclasses import dataclass

from app.providers.base import ProviderHealthStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration constants (with justification)
# ---------------------------------------------------------------------------

# Minimum provider health score to allow ANY new calls.
# Below this, the provider is considered effectively down.
MIN_PROVIDER_HEALTH_FOR_ANY_CALLS = 0.20

# Maximum ratio of unanswered (ringing) calls to available agents.
# 1.0 means if 10 agents are available, at most 10 ringing calls can be in flight.
MAX_UNANSWERED_RATIO = 1.0

# Absolute hard cap on calls in-flight (all non-terminal states).
# Prevents runaway dialing even if the pacing engine goes wrong.
ABSOLUTE_MAX_IN_FLIGHT = 500

# If the answer rate drops below this, fall back to progressive mode.
# Predictive pacing at very low answer rates can dial far too aggressively.
MIN_ANSWER_RATE_FOR_PREDICTIVE = 0.05


class SafetyAction(str, enum.Enum):
    APPROVE = "APPROVE"          # Requested number is safe — proceed as-is
    REDUCE = "REDUCE"            # Requested too many — approving a lower count
    REJECT = "REJECT"            # No calls safe right now
    FALLBACK_TO_PROGRESSIVE = "FALLBACK_TO_PROGRESSIVE"  # Use progressive instead


@dataclass
class SafetyDecision:
    """
    The Safety Controller's verdict on a pacing request.

    Fields
    ------
    action         : What the controller decided.
    approved_calls : The number of calls actually approved (may be < requested).
    requested_calls: The number the pacing engine asked for.
    reason         : Human-readable explanation — very useful for debugging
                     and for interview explanations.
    """
    action: SafetyAction
    approved_calls: int
    requested_calls: int
    reason: str


@dataclass
class SystemSnapshot:
    """
    A read-only snapshot of the current system state.
    The Safety Controller is a pure function of this snapshot + the request.

    Keeping it a dataclass (not live DB queries) means the controller is
    fully testable without a database.
    """
    available_agents: int
    ringing_calls: int
    connected_calls: int
    reserved_calls: int         # Calls reserved but not yet initiated
    answer_rate: float          # Rolling answer rate, 0.0 – 1.0
    provider_health: ProviderHealthStatus
    total_active_calls: int     # All non-terminal calls


class SafetyController:
    """
    Evaluates a pacing request and returns a SafetyDecision.

    This class has NO imports from:
      - app.providers (no direct provider access)
      - app.allocation (no direct allocator access)
      - app.dialer (no pacing logic)

    It only receives a SystemSnapshot and a requested call count.
    This design makes it impossible for the pacing engine to bypass it.
    """

    def evaluate(
        self,
        requested_calls: int,
        snapshot: SystemSnapshot,
    ) -> SafetyDecision:
        """
        Evaluate a pacing request and return a safety decision.

        Parameters
        ----------
        requested_calls : Number of new calls the pacing engine wants to start.
        snapshot        : Current system state snapshot.

        Returns
        -------
        SafetyDecision with action, approved count, and reason.
        """
        # ------------------------------------------------------------------
        # Guard 1: Critical provider failure — reject everything.
        # ------------------------------------------------------------------
        if snapshot.provider_health.health_score < MIN_PROVIDER_HEALTH_FOR_ANY_CALLS:
            return SafetyDecision(
                action=SafetyAction.REJECT,
                approved_calls=0,
                requested_calls=requested_calls,
                reason=(
                    f"Provider health critically low "
                    f"({snapshot.provider_health.health_score:.2f} < "
                    f"{MIN_PROVIDER_HEALTH_FOR_ANY_CALLS}). "
                    f"No new calls allowed."
                ),
            )

        # ------------------------------------------------------------------
        # Guard 2: Absolute hard cap on in-flight calls.
        # ------------------------------------------------------------------
        if snapshot.total_active_calls >= ABSOLUTE_MAX_IN_FLIGHT:
            return SafetyDecision(
                action=SafetyAction.REJECT,
                approved_calls=0,
                requested_calls=requested_calls,
                reason=(
                    f"Total active calls ({snapshot.total_active_calls}) has reached "
                    f"the hard cap ({ABSOLUTE_MAX_IN_FLIGHT})."
                ),
            )

        # ------------------------------------------------------------------
        # Guard 3: Fallback to progressive if answer rate is too low.
        # ------------------------------------------------------------------
        if snapshot.answer_rate < MIN_ANSWER_RATE_FOR_PREDICTIVE:
            # Allow at most 1 call per available agent (progressive behaviour).
            progressive_safe = max(0, snapshot.available_agents - snapshot.ringing_calls)
            approved = min(requested_calls, progressive_safe)
            if approved == 0:
                return SafetyDecision(
                    action=SafetyAction.REJECT,
                    approved_calls=0,
                    requested_calls=requested_calls,
                    reason=(
                        f"Answer rate {snapshot.answer_rate:.1%} below minimum "
                        f"{MIN_ANSWER_RATE_FOR_PREDICTIVE:.1%}. Falling back to "
                        f"progressive — but no agents available."
                    ),
                )
            return SafetyDecision(
                action=SafetyAction.FALLBACK_TO_PROGRESSIVE,
                approved_calls=approved,
                requested_calls=requested_calls,
                reason=(
                    f"Answer rate {snapshot.answer_rate:.1%} below minimum "
                    f"{MIN_ANSWER_RATE_FOR_PREDICTIVE:.1%}. "
                    f"Falling back to progressive mode."
                ),
            )

        # ------------------------------------------------------------------
        # Step 4: Compute max_safe based on agent headroom.
        # ------------------------------------------------------------------
        # Ringing and connected calls already hold agent capacity.
        # We cannot start more calls than we have free agents.
        calls_in_use = snapshot.ringing_calls + snapshot.connected_calls + snapshot.reserved_calls
        max_safe = max(0, snapshot.available_agents - calls_in_use)

        # ------------------------------------------------------------------
        # Step 5: Apply answer-rate guard to prevent too many unanswered calls.
        # ------------------------------------------------------------------
        # If answer rate is low, many ringing calls will not be answered.
        # We cap new calls so ringing calls don't explode beyond available capacity.
        unanswered_cap = math.ceil(snapshot.available_agents * MAX_UNANSWERED_RATIO)
        current_unanswered = snapshot.ringing_calls
        room_under_unanswered_cap = max(0, unanswered_cap - current_unanswered)

        # The candidate is the most conservative of the two limits.
        candidate = min(max_safe, room_under_unanswered_cap)

        # ------------------------------------------------------------------
        # Step 6: Dampen by provider health if degraded.
        # ------------------------------------------------------------------
        # If provider health is degraded (< 0.90), dial proportionally fewer calls.
        if snapshot.provider_health.health_score >= 0.90:
            health_dampened = candidate
        else:
            health_dampened = math.floor(candidate * snapshot.provider_health.health_score)

        # ------------------------------------------------------------------
        # Step 7: Final approved count — cannot exceed requested.
        # ------------------------------------------------------------------
        approved = min(requested_calls, health_dampened)
        approved = max(0, approved)  # Never negative

        # ------------------------------------------------------------------
        # Determine action label.
        # ------------------------------------------------------------------
        if approved == 0:
            action = SafetyAction.REJECT
            reason = (
                f"Approved 0 calls. "
                f"max_safe={max_safe}, unanswered_cap_room={room_under_unanswered_cap}, "
                f"health_score={snapshot.provider_health.health_score:.2f}."
            )
        elif approved < requested_calls:
            action = SafetyAction.REDUCE
            reason = (
                f"Reduced {requested_calls} → {approved}. "
                f"max_safe={max_safe}, "
                f"unanswered_cap_room={room_under_unanswered_cap}, "
                f"health_dampened={health_dampened}, "
                f"provider_health={snapshot.provider_health.health_score:.2f}."
            )
        else:
            action = SafetyAction.APPROVE
            reason = (
                f"Approved {approved} calls. "
                f"max_safe={max_safe}, "
                f"provider_health={snapshot.provider_health.health_score:.2f}."
            )

        logger.info(
            "SafetyController: requested=%d approved=%d action=%s | %s",
            requested_calls, approved, action.value, reason
        )

        return SafetyDecision(
            action=action,
            approved_calls=approved,
            requested_calls=requested_calls,
            reason=reason,
        )
