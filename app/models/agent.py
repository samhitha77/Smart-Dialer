"""
Agent model and state machine.

An agent represents a human debt-collection agent who handles calls.

State machine (see docs/agent_state_machine.md for the full diagram):

  OFFLINE ──► AVAILABLE ──► RESERVED ──► DIALING ──► CONNECTED ──► WRAP_UP ──► AVAILABLE
                  ▲                          │
                  │                          ▼
               PAUSED                   AVAILABLE   (call failed — agent freed)

Invalid transitions are rejected by AgentService.transition_state().
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentState(str, enum.Enum):
    """
    All possible lifecycle states for an agent.
    Using str mixin so the value can be stored directly as a string in SQLite
    and compared without extra conversion.
    """
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"    # Atomically claimed; call not yet initiated
    DIALING = "DIALING"      # Call is being set up by the provider
    CONNECTED = "CONNECTED"  # Agent is on a live call
    WRAP_UP = "WRAP_UP"      # Post-call wrap-up work
    PAUSED = "PAUSED"        # Agent is on a break


# Explicit map of allowed transitions.
# Key   = current state
# Value = set of states the agent is allowed to move to from the current state
AGENT_VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.OFFLINE:    {AgentState.AVAILABLE},
    AgentState.AVAILABLE:  {AgentState.RESERVED, AgentState.PAUSED, AgentState.OFFLINE},
    AgentState.RESERVED:   {AgentState.DIALING, AgentState.AVAILABLE},  # AVAILABLE = reservation released
    AgentState.DIALING:    {AgentState.CONNECTED, AgentState.AVAILABLE},  # AVAILABLE = call failed
    AgentState.CONNECTED:  {AgentState.WRAP_UP},
    AgentState.WRAP_UP:    {AgentState.AVAILABLE, AgentState.OFFLINE},
    AgentState.PAUSED:     {AgentState.AVAILABLE, AgentState.OFFLINE},
}


class Agent(Base):
    """SQLAlchemy ORM model for an agent."""
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Current lifecycle state — stored as a string in the DB.
    state: Mapped[str] = mapped_column(
        Enum(AgentState, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AgentState.OFFLINE.value,
    )

    # Timestamp when the agent was atomically reserved.
    # Used for lease-timeout crash recovery: if a reservation is older than
    # RESERVATION_LEASE_SECONDS, it is automatically released.
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # How long (in seconds) a reservation can be held before it auto-expires.
    # Default: 60 seconds is generous enough for normal call setup.
    reservation_lease_seconds: Mapped[int] = mapped_column(Integer, default=60)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} state={self.state}>"
