"""
CallService — business logic for managing call lifecycle.

Tracks:
  - Active calls (not yet in a terminal state)
  - Ringing calls (provider confirmed ringing but not yet answered)
  - Connected calls (live conversations)

All counts are used by the Safety Controller and Predictive Pacing Engine.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.call import Call, CallState, CALL_VALID_TRANSITIONS, CALL_TERMINAL_STATES


class CallStateError(Exception):
    """Raised when an invalid call state transition is attempted."""


class CallService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_call(self, call_id: int) -> Optional[Call]:
        return self.db.get(Call, call_id)

    def get_call_by_provider_id(self, provider_call_id: str) -> Optional[Call]:
        return (
            self.db.query(Call)
            .filter(Call.provider_call_id == provider_call_id)
            .first()
        )

    def count_active_calls(self) -> int:
        """Calls that are NOT in a terminal state."""
        return (
            self.db.query(Call)
            .filter(Call.state.notin_([s.value for s in CALL_TERMINAL_STATES]))
            .count()
        )

    def count_ringing_calls(self) -> int:
        return (
            self.db.query(Call)
            .filter(Call.state == CallState.RINGING.value)
            .count()
        )

    def count_connected_calls(self) -> int:
        return (
            self.db.query(Call)
            .filter(Call.state.in_([CallState.ANSWERED.value, CallState.CONNECTED.value]))
            .count()
        )

    def count_calls_by_state(self, state: CallState) -> int:
        return (
            self.db.query(Call)
            .filter(Call.state == state.value)
            .count()
        )

    def get_recent_calls(self, limit: int = 100) -> list[Call]:
        """Return the most recent calls — used by pacing engine for answer-rate calculation."""
        return (
            self.db.query(Call)
            .filter(Call.state.in_([
                CallState.COMPLETED.value,
                CallState.FAILED.value,
                CallState.CANCELLED.value,
            ]))
            .order_by(Call.created_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_call(
        self,
        agent_id: int,
        borrower_id: int,
        dialing_mode: str = "progressive",
    ) -> Call:
        """Create a new call in RESERVED state (agent + borrower already reserved)."""
        call = Call(
            agent_id=agent_id,
            borrower_id=borrower_id,
            state=CallState.RESERVED.value,
            dialing_mode=dialing_mode,
        )
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition_state(
        self,
        call_id: int,
        target_state: CallState,
        provider_call_id: Optional[str] = None,
    ) -> Call:
        """
        Move a call to a new state, enforcing the valid transition map.
        Raises CallStateError for invalid transitions.
        """
        call = self.get_call(call_id)
        if call is None:
            raise CallStateError(f"Call {call_id} not found.")

        current = CallState(call.state)
        allowed = CALL_VALID_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            raise CallStateError(
                f"Call {call_id}: transition {current} → {target_state} is not allowed."
            )

        call.state = target_state.value

        # Update provider_call_id if provided (received when call is INITIATED).
        if provider_call_id:
            call.provider_call_id = provider_call_id

        # Record lifecycle timestamps.
        now = datetime.now(timezone.utc)
        if target_state == CallState.INITIATED:
            call.initiated_at = now
        elif target_state in {CallState.ANSWERED, CallState.CONNECTED}:
            if call.answered_at is None:
                call.answered_at = now
        elif target_state in CALL_TERMINAL_STATES:
            call.completed_at = now

        self.db.commit()
        self.db.refresh(call)
        return call

    def calculate_answer_rate(self, sample_size: int = 100) -> float:
        """
        Calculate the rolling answer rate from the most recent completed calls.

        answer_rate = answered_calls / total_completed_calls

        Returns 0.5 as a safe default if there is not enough data yet.
        """
        recent_calls = self.get_recent_calls(limit=sample_size)
        if len(recent_calls) < 5:
            # Not enough data — use a conservative default.
            return 0.5

        answered = sum(
            1 for c in recent_calls
            if c.state in {CallState.COMPLETED.value, CallState.CONNECTED.value}
            and c.answered_at is not None
        )
        return answered / len(recent_calls)
