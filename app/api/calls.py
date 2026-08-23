"""Calls API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.call_service import CallService

router = APIRouter()


class CallResponse(BaseModel):
    id: int
    agent_id: int
    borrower_id: int
    state: str
    provider_call_id: str | None
    dialing_mode: str


@router.get("/", response_model=list[CallResponse])
def list_calls(db: Session = Depends(get_db)):
    from app.models.call import Call
    calls = db.query(Call).order_by(Call.id.desc()).limit(100).all()
    return [
        CallResponse(
            id=c.id, agent_id=c.agent_id, borrower_id=c.borrower_id,
            state=c.state, provider_call_id=c.provider_call_id,
            dialing_mode=c.dialing_mode
        )
        for c in calls
    ]


@router.get("/stats")
def call_stats(db: Session = Depends(get_db)):
    svc = CallService(db)
    return {
        "active": svc.count_active_calls(),
        "ringing": svc.count_ringing_calls(),
        "connected": svc.count_connected_calls(),
        "answer_rate": round(svc.calculate_answer_rate(), 3),
    }
