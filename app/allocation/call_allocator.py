"""
CallAllocator — executes approved calls by sending them to the provider.

Position in the architecture:
  Pacing Engine → Safety Controller → CallAllocator → Provider

The allocator receives the output of the Safety Controller (an approved call
count) and:
  1. Picks an available agent (already reserved by the dialer)
  2. Initiates the call via the provider
  3. Transitions the call to INITIATED state
  4. Handles provider-level failures gracefully

The allocator does NOT make any pacing decisions.
It only acts on what the Safety Controller has approved.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.call import Call, CallState
from app.models.agent import AgentState
from app.models.borrower import BorrowerState
from app.providers.base import TelecomProvider, ProviderCallResult
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    """Result of a single call allocation attempt."""
    success: bool
    call_id: int | None
    provider_call_id: str | None
    error: str | None


class CallAllocator:
    """
    Executes a single call: transitions states and contacts the provider.

    The provider is injected here — this is the ONLY place in the system
    where provider.initiate_call() is called.
    """

    def __init__(self, db: Session, provider: TelecomProvider):
        self.db = db
        self.provider = provider
        self.call_service = CallService(db)
        self.agent_service = AgentService(db)
        self.borrower_service = BorrowerService(db)

    def allocate(self, call: Call, borrower_phone: str) -> AllocationResult:
        """
        Initiate a single pre-reserved call.

        Parameters
        ----------
        call          : A Call object already in RESERVED state.
        borrower_phone: The phone number to dial.

        Returns
        -------
        AllocationResult indicating success or failure.
        """
        call_id = call.id
        agent_id = call.agent_id
        borrower_id = call.borrower_id

        # ------------------------------------------------------------------
        # Step 1: Move agent to DIALING state.
        # ------------------------------------------------------------------
        try:
            self.agent_service.transition_state(agent_id, AgentState.DIALING)
        except Exception as exc:
            # Agent may have gone offline between reservation and allocation.
            logger.warning("Agent %d transition to DIALING failed: %s", agent_id, exc)
            self._fail_call(call_id, agent_id, borrower_id)
            return AllocationResult(
                success=False, call_id=call_id,
                provider_call_id=None,
                error=f"Agent transition failed: {exc}",
            )

        # ------------------------------------------------------------------
        # Step 2: Contact the provider to initiate the call.
        # ------------------------------------------------------------------
        result = self.provider.initiate_call(
            borrower_phone=borrower_phone,
            agent_id=agent_id,
        )

        if result.result != ProviderCallResult.SUCCESS:
            # Provider rejected the call — release resources.
            logger.warning(
                "Provider %s rejected call %d: %s",
                self.provider.name, call_id, result.error_message
            )
            self._fail_call(call_id, agent_id, borrower_id)
            return AllocationResult(
                success=False, call_id=call_id,
                provider_call_id=None,
                error=result.error_message,
            )

        # ------------------------------------------------------------------
        # Step 3: Mark call as INITIATED and record the provider call ID.
        # ------------------------------------------------------------------
        try:
            self.call_service.transition_state(
                call_id,
                CallState.INITIATED,
                provider_call_id=result.provider_call_id,
            )
        except Exception as exc:
            logger.error("Failed to mark call %d as INITIATED: %s", call_id, exc)
            self._fail_call(call_id, agent_id, borrower_id)
            return AllocationResult(
                success=False, call_id=call_id,
                provider_call_id=result.provider_call_id,
                error=str(exc),
            )

        logger.info(
            "Call %d initiated via %s (provider_call_id=%s)",
            call_id, self.provider.name, result.provider_call_id
        )

        return AllocationResult(
            success=True,
            call_id=call_id,
            provider_call_id=result.provider_call_id,
            error=None,
        )

    def _fail_call(self, call_id: int, agent_id: int, borrower_id: int) -> None:
        """
        Mark a call as FAILED and release the agent and borrower.
        Called whenever the allocation process breaks down at any step.
        """
        try:
            self.call_service.transition_state(call_id, CallState.FAILED)
        except Exception:
            pass  # Call may already be in a failed state

        self.agent_service.release_agent(agent_id)
        self.borrower_service.release_borrower(borrower_id)
