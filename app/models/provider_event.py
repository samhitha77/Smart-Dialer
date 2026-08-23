"""
ProviderEvent model — idempotency log.

Every event received from a telecom provider (RINGING, ANSWERED, COMPLETED,
FAILED, TIMEOUT) is recorded here by its unique event_id.

Idempotency rule:
  - If an event_id is NOT in this table → process the event and insert a record.
  - If an event_id IS already in this table → silently discard the duplicate.

This prevents duplicate events from Provider B (or any other chaotic provider)
from causing multiple state transitions for the same call.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProviderEvent(Base):
    """Idempotency log for provider events."""
    __tablename__ = "provider_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique ID assigned by the provider to this event.
    # We use this as the idempotency key.
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Which call this event belongs to.
    call_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Event type string e.g. "RINGING", "ANSWERED", "COMPLETED".
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Whether we actually processed this event (True) or discarded it (False).
    # Discarded = duplicate or invalid transition.
    processed: Mapped[bool] = mapped_column(default=True)

    # Human-readable reason if the event was discarded.
    discard_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderEvent id={self.id} event_id={self.event_id!r} "
            f"call_id={self.call_id} type={self.event_type} "
            f"processed={self.processed}>"
        )
