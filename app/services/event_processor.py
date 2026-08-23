"""
EventProcessor — handles incoming provider events with idempotency and
out-of-order safety.

Two problems to solve:
  1. DUPLICATE EVENTS: Provider B sometimes sends the same event twice.
     Solution: Before processing any event, check if its event_id already
     exists in the provider_events table.  If it does → skip.

  2. OUT-OF-ORDER EVENTS: Provider B sometimes delivers COMPLETED before
     ANSWERED, or ANSWERED before RINGING.
     Solution: Before applying a transition, check CALL_VALID_TRANSITIONS.
     If the transition is not valid → discard the event and log why.

Processing flow for each incoming event:
  ┌─ Is event_id already in provider_events?
  │   YES → record as duplicate, return immediately
  │   NO  → continue
  ├─ Find the call by provider_call_id
  ├─ Is the event_type → CallState transition valid from current state?
  │   NO  → record as out-of-order discard, return
  │   YES → apply the transition
  └─ Update agent / borrower state if needed
"""

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.call import Call, CallState, CALL_VALID_TRANSITIONS, CALL_TERMINAL_STATES
from app.models.provider_event import ProviderEvent
from app.services.agent_service import AgentService
from app.services.borrower_service import BorrowerService
from app.services.call_service import CallService, CallStateError
from app.models.agent import AgentState
from app.models.borrower import BorrowerState

logger = logging.getLogger(__name__)


# Map from provider event_type string to the CallState it represents.
EVENT_TYPE_TO_CALL_STATE: dict[str, CallState] = {
    "RINGING":   CallState.RINGING,
    "ANSWERED":  CallState.ANSWERED,
    "CONNECTED": CallState.CONNECTED,
    "COMPLETED": CallState.COMPLETED,
    "FAILED":    CallState.FAILED,
    "TIMEOUT":   CallState.FAILED,    # Treat timeout as a call failure
    "CANCELLED": CallState.CANCELLED,
}


@dataclass
class EventProcessResult:
    """Result of processing a single provider event."""
    processed: bool           # True = state was updated; False = skipped
    call_id: int | None       # Internal call ID if found
    reason: str               # What happened (for logging / debugging)


class EventProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.call_service = CallService(db)
        self.agent_service = AgentService(db)
        self.borrower_service = BorrowerService(db)

    def process(
        self,
        event_id: str,
        provider_call_id: str,
        event_type: str,
    ) -> EventProcessResult:
        """
        Process a single provider event.

        Parameters
        ----------
        event_id          : Unique ID of this event (from the provider).
        provider_call_id  : The provider's reference to the call.
        event_type        : e.g. "RINGING", "ANSWERED", "COMPLETED", "FAILED".

        Returns an EventProcessResult describing what happened.
        """
        # ------------------------------------------------------------------
        # Step 1: Idempotency check — have we already processed this event?
        # ------------------------------------------------------------------
        existing = (
            self.db.query(ProviderEvent)
            .filter(ProviderEvent.event_id == event_id)
            .first()
        )
        if existing is not None:
            logger.debug("Duplicate event %s — skipping.", event_id)
            return EventProcessResult(
                processed=False,
                call_id=existing.call_id,
                reason=f"Duplicate event_id {event_id}",
            )

        # ------------------------------------------------------------------
        # Step 2: Find the call by provider_call_id
        # ------------------------------------------------------------------
        call = self.call_service.get_call_by_provider_id(provider_call_id)
        if call is None:
            # Unknown call — record and ignore.
            self._record_event(event_id, call_id=-1, event_type=event_type, processed=False,
                               discard_reason=f"Unknown provider_call_id {provider_call_id}")
            return EventProcessResult(
                processed=False,
                call_id=None,
                reason=f"No call found for provider_call_id={provider_call_id}",
            )

        call_id = call.id

        # ------------------------------------------------------------------
        # Step 3: Map event_type to a CallState
        # ------------------------------------------------------------------
        target_state = EVENT_TYPE_TO_CALL_STATE.get(event_type.upper())
        if target_state is None:
            self._record_event(event_id, call_id, event_type, processed=False,
                               discard_reason=f"Unknown event_type {event_type}")
            return EventProcessResult(
                processed=False,
                call_id=call_id,
                reason=f"Unknown event_type: {event_type}",
            )

        # ------------------------------------------------------------------
        # Step 4: Validate the state transition (out-of-order protection)
        # ------------------------------------------------------------------
        current_state = CallState(call.state)

        # If already in a terminal state, discard — no further transitions allowed.
        if current_state in CALL_TERMINAL_STATES:
            self._record_event(event_id, call_id, event_type, processed=False,
                               discard_reason=f"Call already in terminal state {current_state}")
            return EventProcessResult(
                processed=False,
                call_id=call_id,
                reason=f"Call {call_id} is already in terminal state {current_state}.",
            )

        allowed_next_states = CALL_VALID_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_next_states:
            discard_reason = (
                f"Out-of-order: {current_state} → {target_state} not allowed. "
                f"Allowed: {allowed_next_states}"
            )
            logger.warning("Call %d: %s", call_id, discard_reason)
            self._record_event(event_id, call_id, event_type, processed=False,
                               discard_reason=discard_reason)
            return EventProcessResult(
                processed=False,
                call_id=call_id,
                reason=discard_reason,
            )

        # ------------------------------------------------------------------
        # Step 5: Apply the transition
        # ------------------------------------------------------------------
        try:
            self.call_service.transition_state(call_id, target_state)
        except CallStateError as exc:
            # Defensive — should not happen since we checked above.
            self._record_event(event_id, call_id, event_type, processed=False,
                               discard_reason=str(exc))
            return EventProcessResult(processed=False, call_id=call_id, reason=str(exc))

        # ------------------------------------------------------------------
        # Step 6: Side effects — update agent and borrower states accordingly
        # ------------------------------------------------------------------
        self._handle_side_effects(call, target_state)

        # ------------------------------------------------------------------
        # Step 7: Record this event so future duplicates are ignored
        # ------------------------------------------------------------------
        self._record_event(event_id, call_id, event_type, processed=True)

        logger.info(
            "Call %d: event %s → %s applied successfully.",
            call_id, event_type, target_state.value
        )
        return EventProcessResult(
            processed=True,
            call_id=call_id,
            reason=f"Successfully applied {current_state} → {target_state}",
        )

    def _handle_side_effects(self, call: Call, new_call_state: CallState) -> None:
        """
        After a call state change, update the associated agent and borrower.

        Rules:
          RINGING / ANSWERED → agent stays in DIALING (no change needed)
          CONNECTED          → agent moves to CONNECTED; borrower to IN_CALL
          COMPLETED          → agent moves to WRAP_UP; borrower to COMPLETED
          FAILED/CANCELLED   → agent released to AVAILABLE; borrower released to PENDING
        """
        agent_id = call.agent_id
        borrower_id = call.borrower_id

        if new_call_state == CallState.CONNECTED:
            try:
                self.agent_service.transition_state(agent_id, AgentState.CONNECTED)
            except Exception:
                pass  # Agent may already be in CONNECTED from a previous event
            try:
                self.borrower_service.transition_state(borrower_id, BorrowerState.IN_CALL)
            except Exception:
                pass

        elif new_call_state == CallState.COMPLETED:
            try:
                self.agent_service.transition_state(agent_id, AgentState.WRAP_UP)
            except Exception:
                pass
            try:
                self.borrower_service.transition_state(borrower_id, BorrowerState.COMPLETED)
            except Exception:
                pass

        elif new_call_state in {CallState.FAILED, CallState.CANCELLED}:
            # Release both resources so they can be reused.
            self.agent_service.release_agent(agent_id)
            self.borrower_service.release_borrower(borrower_id)

    def _record_event(
        self,
        event_id: str,
        call_id: int,
        event_type: str,
        processed: bool,
        discard_reason: str | None = None,
    ) -> None:
        """Persist the event record for the idempotency log."""
        record = ProviderEvent(
            event_id=event_id,
            call_id=call_id,
            event_type=event_type,
            processed=processed,
            discard_reason=discard_reason,
        )
        try:
            self.db.add(record)
            self.db.commit()
        except IntegrityError:
            # Race condition: another thread inserted the same event_id
            # simultaneously.  Roll back and treat as duplicate.
            self.db.rollback()
            logger.debug("Race on event_id %s — treated as duplicate.", event_id)
