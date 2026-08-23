"""
Call model and state machine.

A call ties one agent to one borrower for one dialing attempt.

State machine (see docs/call_state_machine.md):

  QUEUED ──► RESERVED ──► INITIATED ──► RINGING ──► ANSWERED ──► CONNECTED ──► COMPLETED
                                  │                      │
                                  ▼                      ▼
                               FAILED                FAILED / CANCELLED
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CallState(str, enum.Enum):
    QUEUED = "QUEUED"          # Waiting to be processed
    RESERVED = "RESERVED"      # Agent + borrower reserved; call not yet sent to provider
    INITIATED = "INITIATED"    # Sent to telecom provider; awaiting acknowledgement
    RINGING = "RINGING"        # Provider confirmed the phone is ringing
    ANSWERED = "ANSWERED"      # Borrower picked up; connecting to agent
    CONNECTED = "CONNECTED"    # Live conversation in progress
    COMPLETED = "COMPLETED"    # Call ended normally — terminal
    FAILED = "FAILED"          # Call ended abnormally — terminal
    CANCELLED = "CANCELLED"    # Cancelled before connecting — terminal


# Terminal states — no further transitions allowed.
CALL_TERMINAL_STATES: set[CallState] = {
    CallState.COMPLETED,
    CallState.FAILED,
    CallState.CANCELLED,
}

# Valid transitions map — used by event_processor to reject bad events.
CALL_VALID_TRANSITIONS: dict[CallState, set[CallState]] = {
    CallState.QUEUED:     {CallState.RESERVED, CallState.CANCELLED},
    CallState.RESERVED:   {CallState.INITIATED, CallState.CANCELLED, CallState.FAILED},
    CallState.INITIATED:  {CallState.RINGING, CallState.FAILED, CallState.CANCELLED},
    CallState.RINGING:    {CallState.ANSWERED, CallState.FAILED, CallState.CANCELLED},
    CallState.ANSWERED:   {CallState.CONNECTED, CallState.FAILED},
    CallState.CONNECTED:  {CallState.COMPLETED, CallState.FAILED},
    CallState.COMPLETED:  set(),  # Terminal
    CallState.FAILED:     set(),  # Terminal
    CallState.CANCELLED:  set(),  # Terminal
}


class Call(Base):
    """SQLAlchemy ORM model for a single dialing attempt."""
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys to the agent and borrower involved in this call.
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), nullable=False)
    borrower_id: Mapped[int] = mapped_column(Integer, ForeignKey("borrowers.id"), nullable=False)

    state: Mapped[str] = mapped_column(
        Enum(CallState, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CallState.QUEUED.value,
    )

    # Unique identifier returned by the telecom provider when a call is initiated.
    # Used to correlate provider webhook events back to this call record.
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Which dialing mode started this call.
    dialing_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="progressive"
    )

    # Timestamps for key lifecycle events — useful for metrics.
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Call id={self.id} agent={self.agent_id} "
            f"borrower={self.borrower_id} state={self.state}>"
        )
