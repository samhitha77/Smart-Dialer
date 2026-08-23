"""
Borrower model.

A borrower is a person who owes money and is on the dialing campaign list.

State machine:
  PENDING ──► RESERVED ──► IN_CALL ──► COMPLETED
                  │
                  ▼
               PENDING  (released if call fails before connecting)

A borrower can only be in one active call at a time.
Reservation uses the same atomic UPDATE rowcount pattern as agents.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BorrowerState(str, enum.Enum):
    PENDING = "PENDING"       # Waiting to be called
    RESERVED = "RESERVED"     # Atomically claimed; call not yet initiated
    IN_CALL = "IN_CALL"       # Currently on a call
    COMPLETED = "COMPLETED"   # Successfully contacted; no further calls needed
    DO_NOT_CALL = "DO_NOT_CALL"  # Must never be dialed (opt-out)


BORROWER_VALID_TRANSITIONS: dict[BorrowerState, set[BorrowerState]] = {
    BorrowerState.PENDING:      {BorrowerState.RESERVED},
    BorrowerState.RESERVED:     {BorrowerState.IN_CALL, BorrowerState.PENDING},  # PENDING = released
    BorrowerState.IN_CALL:      {BorrowerState.COMPLETED, BorrowerState.PENDING},  # PENDING = retry eligible
    BorrowerState.COMPLETED:    set(),  # Terminal state
    BorrowerState.DO_NOT_CALL:  set(),  # Terminal state
}


class Borrower(Base):
    """SQLAlchemy ORM model for a borrower (campaign contact)."""
    __tablename__ = "borrowers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)

    state: Mapped[str] = mapped_column(
        Enum(BorrowerState, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=BorrowerState.PENDING.value,
    )

    # Lease timestamp — same crash-recovery pattern as agents.
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reservation_lease_seconds: Mapped[int] = mapped_column(Integer, default=60)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Borrower id={self.id} name={self.name!r} state={self.state}>"
