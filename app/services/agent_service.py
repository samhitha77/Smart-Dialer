"""
AgentService — business logic for agent lifecycle management.

Key responsibility: concurrency-safe reservation.

The atomic reservation works like this:
  1. Issue:
       UPDATE agents SET state='RESERVED', reserved_at=<now>
       WHERE id=<id> AND state='AVAILABLE'
  2. Check how many rows were actually updated (rowcount).
  3. If rowcount == 1  → this thread/process won the race → reservation succeeded.
  4. If rowcount == 0  → another thread already reserved this agent → we lost → fail cleanly.

This guarantee comes from SQLite's serialised write locking:
only one writer can modify the row at a time.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentState, AGENT_VALID_TRANSITIONS


class AgentStateError(Exception):
    """Raised when an invalid state transition is attempted."""


class AgentService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: int) -> Optional[Agent]:
        return self.db.get(Agent, agent_id)

    def get_available_agents(self) -> list[Agent]:
        """Return all agents currently in the AVAILABLE state."""
        return (
            self.db.query(Agent)
            .filter(Agent.state == AgentState.AVAILABLE.value)
            .all()
        )

    def count_available_agents(self) -> int:
        return (
            self.db.query(Agent)
            .filter(Agent.state == AgentState.AVAILABLE.value)
            .count()
        )

    # ------------------------------------------------------------------
    # State transitions (validated)
    # ------------------------------------------------------------------

    def create_agent(self, name: str) -> Agent:
        agent = Agent(name=name, state=AgentState.OFFLINE.value)
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def transition_state(
        self,
        agent_id: int,
        target_state: AgentState,
    ) -> Agent:
        """
        Transition an agent to a new state, enforcing the valid transition map.
        Raises AgentStateError if the transition is not allowed.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            raise AgentStateError(f"Agent {agent_id} not found.")

        current = AgentState(agent.state)
        allowed = AGENT_VALID_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            raise AgentStateError(
                f"Agent {agent_id}: transition {current} → {target_state} is not allowed. "
                f"Allowed from {current}: {allowed}"
            )

        agent.state = target_state.value

        # Clear the reservation lease timestamp when leaving reserved/dialing states.
        if target_state not in {AgentState.RESERVED, AgentState.DIALING}:
            agent.reserved_at = None

        self.db.commit()
        self.db.refresh(agent)
        return agent

    # ------------------------------------------------------------------
    # Atomic reservation (STEP 5 — concurrency-safe)
    # ------------------------------------------------------------------

    def atomic_reserve(self, agent_id: int) -> bool:
        """
        Attempt to atomically reserve an agent.

        Returns True  if the agent was successfully reserved (we won the race).
        Returns False if the agent was already taken (we lost the race).

        The SQL equivalent is:
            UPDATE agents
            SET state = 'RESERVED', reserved_at = NOW()
            WHERE id = <agent_id> AND state = 'AVAILABLE';

        Checking rowcount tells us whether our update actually changed anything.
        """
        now = datetime.now(timezone.utc)
        result = self.db.execute(
            update(Agent)
            .where(Agent.id == agent_id, Agent.state == AgentState.AVAILABLE.value)
            .values(state=AgentState.RESERVED.value, reserved_at=now)
        )
        self.db.commit()
        # result.rowcount == 1 → we updated the row → we won
        # result.rowcount == 0 → someone else already changed the state
        return result.rowcount == 1

    def release_agent(self, agent_id: int) -> None:
        """
        Release a reserved or dialing agent back to AVAILABLE.
        Called when a call fails before connecting, or on crash recovery.
        """
        self.db.execute(
            update(Agent)
            .where(
                Agent.id == agent_id,
                Agent.state.in_([AgentState.RESERVED.value, AgentState.DIALING.value]),
            )
            .values(state=AgentState.AVAILABLE.value, reserved_at=None)
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Crash recovery — lease expiry
    # ------------------------------------------------------------------

    def expire_stale_reservations(self) -> int:
        """
        Release any agent reservations that have been held longer than their
        lease duration.  This handles the case where a worker crashes after
        reserving an agent but before initiating a call.

        Returns the number of agents whose reservations were expired.
        """
        now = datetime.now(timezone.utc)
        agents = (
            self.db.query(Agent)
            .filter(
                Agent.state.in_([AgentState.RESERVED.value, AgentState.DIALING.value]),
                Agent.reserved_at.isnot(None),
            )
            .all()
        )

        expired_count = 0
        for agent in agents:
            res_at = agent.reserved_at
            if res_at.tzinfo is None:
                res_at = res_at.replace(tzinfo=timezone.utc)
            lease_expiry = res_at + timedelta(seconds=agent.reservation_lease_seconds)
            if now >= lease_expiry:
                agent.state = AgentState.AVAILABLE.value
                agent.reserved_at = None
                expired_count += 1

        if expired_count > 0:
            self.db.commit()

        return expired_count
