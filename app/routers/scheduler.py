# app/routers/schedule_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session
from app.db.session import get_session
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug
from app.services.scheduler_service import SchedulerService
from app.services.enhanced_scheduler_service import EnhancedSchedulerService
from app.validators.scheduling_validators import ScheduleRequestValidator
from pydantic import ValidationError

router = APIRouter(prefix="/{org_slug}/schedule", tags=["Scheduler"])
security = HTTPBearer()

@router.post("/run-weekly")
def run_weekly(org_slug: str, payload: dict = None, session: Session = Depends(get_session), current: dict = Depends(get_current_user)):
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")
    org = get_org_by_slug(org_slug, session)
    use_cpsat = bool(payload.get("use_cpsat", False)) if payload else False
    result = SchedulerService.run_weekly(session, org.id, use_cpsat=use_cpsat)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason"))
    return result

@router.post("/run-monthly")
def run_monthly(org_slug: str, payload: dict = None, session: Session = Depends(get_session), current: dict = Depends(get_current_user)):
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")
    org = get_org_by_slug(org_slug, session)
    use_cpsat = bool(payload.get("use_cpsat", False)) if payload else False
    result = SchedulerService.run_monthly(session, org.id, use_cpsat=use_cpsat)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason"))
    return result

@router.post("/run")
def run_enhanced_schedule(org_slug: str, payload: dict = None, session: Session = Depends(get_session), current: dict = Depends(get_current_user)):
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")
    org = get_org_by_slug(org_slug, session)

    # Validate payload exists
    if not payload:
        raise HTTPException(400, "Request body is required with 'start_date' and 'end_date' fields")

    start = payload.get("start_date")
    end = payload.get("end_date")
    
    # Validate required fields
    if not start or not end:
        raise HTTPException(400, "Both 'start_date' and 'end_date' are required in the request body")
    
    use_cpsat = bool(payload.get("use_cpsat", False))
    cpsat_time = int(payload.get("cpsat_time", 30))
    max_shifts_per_day = payload.get("max_shifts_per_day", 1)
    max_work_days_per_week = payload.get("max_work_days_per_week", 5)

    try:
        from datetime import date
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except Exception:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    result = EnhancedSchedulerService.run_schedule_with_details(
        session=session,
        org_id=org.id,
        start_date=s,
        end_date=e,
        use_cpsat=use_cpsat,
        cpsat_time=cpsat_time,
        max_shifts_per_day=max_shifts_per_day,
        max_work_days_per_week=max_work_days_per_week
    )

    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "Scheduler failed"))
    return result
