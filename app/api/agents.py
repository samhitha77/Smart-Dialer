"""Agents API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import AgentState
from app.services.agent_service import AgentService, AgentStateError

router = APIRouter()


class CreateAgentRequest(BaseModel):
    name: str


class AgentResponse(BaseModel):
    id: int
    name: str
    state: str


@router.post("/", response_model=AgentResponse, status_code=201)
def create_agent(body: CreateAgentRequest, db: Session = Depends(get_db)):
    svc = AgentService(db)
    agent = svc.create_agent(body.name)
    # New agents start OFFLINE; move to AVAILABLE immediately.
    agent = svc.transition_state(agent.id, AgentState.AVAILABLE)
    return AgentResponse(id=agent.id, name=agent.name, state=agent.state)


@router.get("/", response_model=list[AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    from app.models.agent import Agent
    agents = db.query(Agent).all()
    return [AgentResponse(id=a.id, name=a.name, state=a.state) for a in agents]


@router.get("/available", response_model=list[AgentResponse])
def list_available_agents(db: Session = Depends(get_db)):
    svc = AgentService(db)
    agents = svc.get_available_agents()
    return [AgentResponse(id=a.id, name=a.name, state=a.state) for a in agents]


@router.post("/{agent_id}/transition")
def transition_agent(agent_id: int, target_state: str, db: Session = Depends(get_db)):
    svc = AgentService(db)
    try:
        state = AgentState(target_state.upper())
        agent = svc.transition_state(agent_id, state)
        return {"id": agent.id, "state": agent.state}
    except (ValueError, AgentStateError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
