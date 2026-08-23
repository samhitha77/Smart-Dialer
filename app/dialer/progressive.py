"""
Progressive Dialer — the simplest and safest dialing strategy.

Core rule:
  New calls initiated ≤ number of currently AVAILABLE agents.

This is the safest mode because there is a 1:1 guarantee:
  Every new outbound call has a specific agent waiting to receive it.

Algorithm per dialing cycle:
  1. Count available agents → n_available.
  2. Count current active calls (non-terminal) → n_active.
  3. The maximum new calls we can safely start = n_available.
     (We do not need to subtract n_active here because each active call
      already has its agent in a non-AVAILABLE state.  Available agents
      are genuinely free.)
  4. Ask the Safety Controller to approve this count.
     (Even in progressive mode, the Safety Controller can reduce or reject
     the request based on provider health or hard caps.)
  5. For each approved slot:
       a. Pick an eligible borrower.
       b. Atomically reserve the agent.
       c. Atomically reserve the borrower.
       d. Create a RESERVED call record.
       e. Pass to CallAllocator to initiate.
       f. If anything fails, release the resources.

This module does NOT call the provider directly.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService
from app.allocation.call_allocator import CallAllocator, AllocationResult
from app.safety.safety_controller import SafetyController, SystemSnapshot
from app.providers.base import TelecomProvider

logger = logging.getLogger(__name__)


@dataclass
class ProgressiveDialResult:
    """Summary of a single progressive dialing cycle."""
    attempted: int = 0      # Number of calls we tried to initiate
    succeeded: int = 0      # Calls successfully handed to provider
    failed: int = 0         # Calls that failed during allocation
    skipped: int = 0        # Slots skipped (no borrowers or agents available)
    safety_approved: int = 0
    safety_action: str = ""
    safety_reason: str = ""
    errors: list[str] = field(default_factory=list)


class ProgressiveDialer:
    """
    Runs one cycle of progressive dialing.

    One cycle = one pass through the available agent pool.
    In production this would run on a schedule (e.g. every 2 seconds).
    """

    def __init__(self, db: Session, provider: TelecomProvider):
        self.db = db
        self.provider = provider
        self.agent_service = AgentService(db)
        self.borrower_service = BorrowerService(db)
        self.call_service = CallService(db)
        self.allocator = CallAllocator(db, provider)
        self.safety_controller = SafetyController()

    def run_cycle(self) -> ProgressiveDialResult:
        """
        Execute one progressive dialing cycle.

        Returns a summary of what happened.
        """
        result = ProgressiveDialResult()

        # ------------------------------------------------------------------
        # Step 1: How many agents are genuinely available right now?
        # ------------------------------------------------------------------
        available_agents = self.agent_service.get_available_agents()
        n_available = len(available_agents)

        if n_available == 0:
            logger.debug("Progressive cycle: no available agents.")
            result.safety_action = "SKIP"
            result.safety_reason = "No available agents."
            return result

        # ------------------------------------------------------------------
        # Step 2: Ask the Safety Controller to approve.
        # Even progressive mode goes through Safety Controller.
        # ------------------------------------------------------------------
        snapshot = self._build_snapshot()
        safety_decision = self.safety_controller.evaluate(
            requested_calls=n_available,
            snapshot=snapshot,
        )
        result.safety_approved = safety_decision.approved_calls
        result.safety_action = safety_decision.action.value
        result.safety_reason = safety_decision.reason

        if safety_decision.approved_calls == 0:
            logger.info(
                "Progressive cycle: Safety Controller rejected all calls. %s",
                safety_decision.reason
            )
            return result

        # ------------------------------------------------------------------
        # Step 3: Initiate up to safety_decision.approved_calls calls.
        # ------------------------------------------------------------------
        approved_count = safety_decision.approved_calls

        # Get pending borrowers — fetch a batch big enough to cover approved slots.
        pending_borrowers = self.borrower_service.get_pending_borrowers(limit=approved_count * 2)

        borrower_iter = iter(pending_borrowers)

        for agent in available_agents[:approved_count]:
            # Try to get a borrower.
            borrower = next(borrower_iter, None)
            if borrower is None:
                result.skipped += 1
                logger.debug("Progressive cycle: no borrower available for agent %d.", agent.id)
                continue

            # Atomically reserve the agent.
            agent_reserved = self.agent_service.atomic_reserve(agent.id)
            if not agent_reserved:
                # Another worker beat us to this agent.
                result.skipped += 1
                logger.debug("Progressive cycle: agent %d already taken.", agent.id)
                continue

            # Atomically reserve the borrower.
            borrower_reserved = self.borrower_service.atomic_reserve(borrower.id)
            if not borrower_reserved:
                # Another worker grabbed this borrower — release the agent and try next.
                self.agent_service.release_agent(agent.id)
                result.skipped += 1
                logger.debug("Progressive cycle: borrower %d already taken.", borrower.id)
                continue

            # Create the call record in RESERVED state.
            call = self.call_service.create_call(
                agent_id=agent.id,
                borrower_id=borrower.id,
                dialing_mode="progressive",
            )

            # Hand off to the Call Allocator.
            alloc_result: AllocationResult = self.allocator.allocate(
                call=call,
                borrower_phone=borrower.phone_number,
            )

            result.attempted += 1
            if alloc_result.success:
                result.succeeded += 1
            else:
                result.failed += 1
                result.errors.append(
                    f"Call {call.id} failed: {alloc_result.error}"
                )

        logger.info(
            "Progressive cycle complete: attempted=%d succeeded=%d failed=%d skipped=%d",
            result.attempted, result.succeeded, result.failed, result.skipped
        )
        return result

    def _build_snapshot(self) -> SystemSnapshot:
        """Collect the current system state for the Safety Controller."""
        from app.models.call import CallState as _CallState
        return SystemSnapshot(
            available_agents=self.agent_service.count_available_agents(),
            ringing_calls=self.call_service.count_ringing_calls(),
            connected_calls=self.call_service.count_connected_calls(),
            reserved_calls=self.call_service.count_calls_by_state(_CallState.RESERVED),
            answer_rate=self.call_service.calculate_answer_rate(),
            provider_health=self.provider.get_health(),
            total_active_calls=self.call_service.count_active_calls(),
        )
