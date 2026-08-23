"""Dialer API router — triggers progressive and predictive dialing cycles."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.dialer.progressive import ProgressiveDialer
from app.dialer.predictive import PredictivePacingEngine

router = APIRouter()

# Module-level provider instances (shared state for prototype).
_provider_a = ProviderA()
_provider_b = ProviderB()


@router.post("/progressive/cycle")
def run_progressive_cycle(provider: str = "a", db: Session = Depends(get_db)):
    """Run one cycle of the progressive dialer."""
    prov = _provider_b if provider.lower() == "b" else _provider_a
    dialer = ProgressiveDialer(db, prov)
    result = dialer.run_cycle()
    return {
        "mode": "progressive",
        "attempted": result.attempted,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "skipped": result.skipped,
        "safety_approved": result.safety_approved,
        "safety_action": result.safety_action,
        "safety_reason": result.safety_reason,
    }


@router.get("/predictive/recommend")
def get_predictive_recommendation(provider: str = "a", db: Session = Depends(get_db)):
    """Get a predictive pacing recommendation (without initiating calls)."""
    prov = _provider_b if provider.lower() == "b" else _provider_a
    engine = PredictivePacingEngine(db, prov)
    rec, safety = engine.recommend_and_evaluate()
    return {
        "recommendation": {
            "recommended_calls": rec.recommended_calls,
            "reason": rec.reason,
        },
        "safety_decision": {
            "action": safety.action.value,
            "approved_calls": safety.approved_calls,
            "reason": safety.reason,
        },
    }
