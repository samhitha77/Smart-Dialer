"""Borrowers API router."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.borrower_service import BorrowerService

router = APIRouter()


class CreateBorrowerRequest(BaseModel):
    name: str
    phone_number: str


class BorrowerResponse(BaseModel):
    id: int
    name: str
    phone_number: str
    state: str


@router.post("/", response_model=BorrowerResponse, status_code=201)
def create_borrower(body: CreateBorrowerRequest, db: Session = Depends(get_db)):
    svc = BorrowerService(db)
    b = svc.create_borrower(body.name, body.phone_number)
    return BorrowerResponse(id=b.id, name=b.name, phone_number=b.phone_number, state=b.state)


@router.get("/", response_model=list[BorrowerResponse])
def list_borrowers(db: Session = Depends(get_db)):
    from app.models.borrower import Borrower
    borrowers = db.query(Borrower).limit(100).all()
    return [BorrowerResponse(id=b.id, name=b.name, phone_number=b.phone_number, state=b.state)
            for b in borrowers]
