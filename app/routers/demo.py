# app/routers/demo.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlmodel import Session
from typing import Optional
from pydantic import BaseModel
from app.db.session import get_session
from app.utils.seed_demo import seed_demo

router = APIRouter(prefix="/demo", tags=["demo"])

class SeedRequest(BaseModel):
    demo_type: Optional[str] = "basic"
    days: Optional[int] = 7

@router.post("/seed")
def seed_endpoint(request: SeedRequest, session: Session = Depends(get_session)):
    """
    demo_type: one of ['basic','heavy_conflict','last_minute_leave']
    days: planning window (days)
    """
    demo_type = request.demo_type
    days = request.days
    supported = {"basic","heavy_conflict","last_minute_leave"}
    if demo_type not in supported:
        raise HTTPException(status_code=400, detail=f"demo_type must be one of {supported}")
    payload = seed_demo(demo_type, days)
    return {"status":"ok", "payload": payload}
