"""
Predictive Pacing Engine — recommends how many calls to initiate.

IMPORTANT: This module never calls the provider.
It only produces a recommendation (a number).
That recommendation is then evaluated by the Safety Controller before
any calls are actually made.

Predictive vs Progressive
─────────────────────────
Progressive: "I have 10 free agents → I'll start 10 calls."
Predictive:  "I have 10 free agents, but only 40% answer rate →
              I need to dial 25 numbers to get 10 answered calls."

The formula (pipeline-fill model)
──────────────────────────────────
We want exactly `target_connected` agents to be on live calls.
Given the answer_rate, to get that many connections we need:

  calls_to_start = ceil(target_connected / answer_rate)

Where:
  target_connected = available_agents - current_connections

But we also have calls already in-flight (ringing) that haven't answered yet.
Their expected connections are:
  expected_from_ringing = ringing_calls * answer_rate

So the adjusted formula is:
  target_connected  = available_agents - connected_calls
  calls_needed      = ceil(target_connected / answer_rate)
  already_in_flight = ringing_calls
  expected_from_ringing = floor(already_in_flight * answer_rate)
  new_calls_needed  = max(0, ceil((target_connected - expected_from_ringing) / answer_rate))

  # Apply provider health dampener: dial less aggressively when provider is sick.
  recommended = floor(new_calls_needed * provider_health_score)

All maths is standard integer arithmetic — no ML required.
The formula is deterministic: same inputs → same output every time.
"""

import math
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.providers.base import TelecomProvider
from app.services.agent_service import AgentService
from app.services.call_service import CallService
from app.models.call import CallState
from app.safety.safety_controller import SafetyController, SystemSnapshot, SafetyDecision

logger = logging.getLogger(__name__)


@dataclass
class PacingRecommendation:
    """
    Output of the Predictive Pacing Engine.

    recommended_calls: How many new calls the engine thinks should be started.
    reason           : Human-readable walkthrough of the calculation — essential
                       for interview explanations.
    """
    recommended_calls: int
    available_agents: int
    connected_calls: int
    ringing_calls: int
    answer_rate: float
    provider_health_score: float
    reason: str


class PredictivePacingEngine:
    """
    Calculates the recommended number of new calls to initiate.

    This class:
      - Has access to the DB (to read system state).
      - Has access to the provider (read-only health check only).
      - Has access to the Safety Controller (to pass its recommendation through).
      - Does NOT call provider.initiate_call() directly.
      - Does NOT call the Call Allocator directly.

    After producing a recommendation, the dialer passes it to the Safety
    Controller, which produces the final approved count.
    """

    def __init__(self, db: Session, provider: TelecomProvider):
        self.db = db
        self.provider = provider
        self.agent_service = AgentService(db)
        self.call_service = CallService(db)
        self.safety_controller = SafetyController()

    def recommend(self) -> PacingRecommendation:
        """
        Calculate the recommended number of new calls to start this cycle.

        Returns a PacingRecommendation — NOT an approved count.
        The recommendation must still pass through the Safety Controller.
        """
        # ------------------------------------------------------------------
        # Gather current system state.
        # ------------------------------------------------------------------
        available_agents = self.agent_service.count_available_agents()
        connected_calls = self.call_service.count_connected_calls()
        ringing_calls = self.call_service.count_ringing_calls()
        answer_rate = self.call_service.calculate_answer_rate()
        provider_health = self.provider.get_health()

        # ------------------------------------------------------------------
        # Guard: if no agents are available, recommend 0.
        # ------------------------------------------------------------------
        if available_agents == 0:
            return PacingRecommendation(
                recommended_calls=0,
                available_agents=0,
                connected_calls=connected_calls,
                ringing_calls=ringing_calls,
                answer_rate=answer_rate,
                provider_health_score=provider_health.health_score,
                reason="No available agents — recommend 0 calls.",
            )

        # ------------------------------------------------------------------
        # Guard: if answer_rate is 0, we cannot divide — fall back to 1 call.
        # ------------------------------------------------------------------
        if answer_rate <= 0.0:
            return PacingRecommendation(
                recommended_calls=1,
                available_agents=available_agents,
                connected_calls=connected_calls,
                ringing_calls=ringing_calls,
                answer_rate=answer_rate,
                provider_health_score=provider_health.health_score,
                reason="Answer rate is 0 — safely recommending 1 call only.",
            )

        # ------------------------------------------------------------------
        # Core pipeline-fill formula.
        # ------------------------------------------------------------------

        # How many more connections do we want to fill our available agents?
        # We target having ALL available agents on calls.
        target_new_connections = available_agents - connected_calls
        target_new_connections = max(0, target_new_connections)

        # Of the currently ringing calls, how many do we expect to be answered?
        expected_from_ringing = math.floor(ringing_calls * answer_rate)

        # Remaining connections we still need to generate.
        connections_still_needed = max(0, target_new_connections - expected_from_ringing)

        # To get `connections_still_needed` answers at the current answer_rate,
        # we need to initiate this many calls:
        #   calls_needed = connections_still_needed / answer_rate
        #   (ceiling because we round up — better to have one extra than one short)
        if connections_still_needed == 0:
            calls_needed = 0
        else:
            calls_needed = math.ceil(connections_still_needed / answer_rate)

        # ------------------------------------------------------------------
        # Dampen by provider health.
        # ------------------------------------------------------------------
        # If the provider health is 0.6 (60%), we dial only 60% of what we'd
        # otherwise dial.  This naturally reduces load on a struggling provider.
        health_dampened = math.floor(calls_needed * provider_health.health_score)

        # ------------------------------------------------------------------
        # Build the explanation (very useful for debugging and interviews).
        # ------------------------------------------------------------------
        reason = (
            f"available_agents={available_agents}, "
            f"connected_calls={connected_calls}, "
            f"ringing_calls={ringing_calls}, "
            f"answer_rate={answer_rate:.2%}, "
            f"target_new_connections={target_new_connections}, "
            f"expected_from_ringing={expected_from_ringing}, "
            f"connections_still_needed={connections_still_needed}, "
            f"calls_needed={calls_needed}, "
            f"provider_health={provider_health.health_score:.2f}, "
            f"health_dampened={health_dampened}. "
            f"Recommending {health_dampened} calls."
        )

        logger.info("PredictivePacingEngine recommendation: %d | %s", health_dampened, reason)

        return PacingRecommendation(
            recommended_calls=health_dampened,
            available_agents=available_agents,
            connected_calls=connected_calls,
            ringing_calls=ringing_calls,
            answer_rate=answer_rate,
            provider_health_score=provider_health.health_score,
            reason=reason,
        )

    def recommend_and_evaluate(self) -> tuple[PacingRecommendation, SafetyDecision]:
        """
        Convenience method: get a recommendation AND run it through Safety Controller.

        Returns (recommendation, safety_decision).
        Use safety_decision.approved_calls as the actual call count to initiate.
        """
        recommendation = self.recommend()
        snapshot = self._build_snapshot(recommendation)
        safety_decision = self.safety_controller.evaluate(
            requested_calls=recommendation.recommended_calls,
            snapshot=snapshot,
        )
        return recommendation, safety_decision

    def _build_snapshot(self, rec: PacingRecommendation) -> SystemSnapshot:
        """Build a SystemSnapshot from the recommendation data."""
        return SystemSnapshot(
            available_agents=rec.available_agents,
            ringing_calls=rec.ringing_calls,
            connected_calls=rec.connected_calls,
            reserved_calls=self.call_service.count_calls_by_state(CallState.RESERVED),
            answer_rate=rec.answer_rate,
            provider_health=self.provider.get_health(),
            total_active_calls=self.call_service.count_active_calls(),
        )
