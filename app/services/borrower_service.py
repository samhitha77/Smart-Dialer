"""
BorrowerService — business logic for borrower lifecycle management.

Uses the same atomic reservation pattern as AgentService to ensure that
two workers cannot allocate the same borrower to two different calls.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.borrower import Borrower, BorrowerState, BORROWER_VALID_TRANSITIONS


class BorrowerStateError(Exception):
    """Raised when an invalid borrower state transition is attempted."""


class BorrowerService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_borrower(self, borrower_id: int) -> Optional[Borrower]:
        return self.db.get(Borrower, borrower_id)

    def get_pending_borrowers(self, limit: int = 50) -> list[Borrower]:
        """Return borrowers waiting to be called, ordered by creation time."""
        return (
            self.db.query(Borrower)
            .filter(Borrower.state == BorrowerState.PENDING.value)
            .order_by(Borrower.created_at.asc())
            .limit(limit)
            .all()
        )

    def count_pending_borrowers(self) -> int:
        return (
            self.db.query(Borrower)
            .filter(Borrower.state == BorrowerState.PENDING.value)
            .count()
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_borrower(self, name: str, phone_number: str) -> Borrower:
        borrower = Borrower(
            name=name,
            phone_number=phone_number,
            state=BorrowerState.PENDING.value,
        )
        self.db.add(borrower)
        self.db.commit()
        self.db.refresh(borrower)
        return borrower

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition_state(self, borrower_id: int, target_state: BorrowerState) -> Borrower:
        borrower = self.get_borrower(borrower_id)
        if borrower is None:
            raise BorrowerStateError(f"Borrower {borrower_id} not found.")

        current = BorrowerState(borrower.state)
        allowed = BORROWER_VALID_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            raise BorrowerStateError(
                f"Borrower {borrower_id}: transition {current} → {target_state} is not allowed."
            )

        borrower.state = target_state.value
        if target_state not in {BorrowerState.RESERVED, BorrowerState.IN_CALL}:
            borrower.reserved_at = None

        self.db.commit()
        self.db.refresh(borrower)
        return borrower

    # ------------------------------------------------------------------
    # Atomic reservation
    # ------------------------------------------------------------------

    def atomic_reserve(self, borrower_id: int) -> bool:
        """
        Atomically reserve a borrower.  Same rowcount trick as agent reservation.
        Returns True if we won the race, False otherwise.
        """
        now = datetime.now(timezone.utc)
        result = self.db.execute(
            update(Borrower)
            .where(Borrower.id == borrower_id, Borrower.state == BorrowerState.PENDING.value)
            .values(state=BorrowerState.RESERVED.value, reserved_at=now)
        )
        self.db.commit()
        return result.rowcount == 1

    def release_borrower(self, borrower_id: int) -> None:
        """Release a reserved borrower back to PENDING (call failed before connecting)."""
        self.db.execute(
            update(Borrower)
            .where(
                Borrower.id == borrower_id,
                Borrower.state.in_([BorrowerState.RESERVED.value, BorrowerState.IN_CALL.value]),
            )
            .values(state=BorrowerState.PENDING.value, reserved_at=None)
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    def expire_stale_reservations(self) -> int:
        """Release borrower reservations that have exceeded their lease duration."""
        borrowers = (
            self.db.query(Borrower)
            .filter(
                Borrower.state == BorrowerState.RESERVED.value,
                Borrower.reserved_at.isnot(None),
            )
            .all()
        )

        expired_count = 0
        now = datetime.now(timezone.utc)
        for borrower in borrowers:
            res_at = borrower.reserved_at
            if res_at.tzinfo is None:
                res_at = res_at.replace(tzinfo=timezone.utc)
            lease_expiry = res_at + timedelta(seconds=borrower.reservation_lease_seconds)
            if now >= lease_expiry:
                borrower.state = BorrowerState.PENDING.value
                borrower.reserved_at = None
                expired_count += 1

        if expired_count > 0:
            self.db.commit()

        return expired_count
