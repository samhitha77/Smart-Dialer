"""Events API router — receives provider webhook events."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.event_processor import EventProcessor

router = APIRouter()


class ProviderEventRequest(BaseModel):
    event_id: str
    provider_call_id: str
    event_type: str


@router.post("/provider-webhook")
def handle_provider_event(body: ProviderEventRequest, db: Session = Depends(get_db)):
    """
    Endpoint for receiving real-time events from telecom providers.
    Handles idempotency and out-of-order events automatically.
    """
    processor = EventProcessor(db)
    result = processor.process(
        event_id=body.event_id,
        provider_call_id=body.provider_call_id,
        event_type=body.event_type,
    )
    return {
        "processed": result.processed,
        "call_id": result.call_id,
        "reason": result.reason,
    }


@router.get("/", response_model=list[dict])
def list_events(db: Session = Depends(get_db)):
    """List recent provider webhook events logged in the system."""
    from app.models.provider_event import ProviderEvent
    events = db.query(ProviderEvent).order_by(ProviderEvent.id.desc()).limit(100).all()
    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "call_id": e.call_id,
            "event_type": e.event_type,
            "processed": e.processed,
            "discard_reason": e.discard_reason,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in events
    ]
