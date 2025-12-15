# app/routers/shift_generator_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlmodel import Session
from datetime import date

from app.core.security import get_current_user
from app.db.session import get_session
from app.utils.organization_lookup import get_org_by_slug
from app.scheduler_engine.services.shift_generator import ShiftGeneratorService

router = APIRouter(prefix="/{org_slug}/shift-generator", tags=["Shift Generator"])

@router.post("")
def generate_shifts(
    org_slug: str,
    payload: dict,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)

    start = date.fromisoformat(payload["start_date"])
    end = date.fromisoformat(payload["end_date"])

    dept_rules = payload.get("departments", [])
    pipelines = payload.get("pipelines", [])

    created_dept_shifts = ShiftGeneratorService.generate_dept_shifts(
        session, org.id, dept_rules, start, end
    )

    created_pipe_shifts = ShiftGeneratorService.generate_pipeline_shifts(
        session, org.id, pipelines, start, end
    )

    return {
        "ok": True,
        "summary": {
            "department_shifts_created": len(created_dept_shifts),
            "pipeline_shifts_created": len(created_pipe_shifts),
            "total": len(created_dept_shifts) + len(created_pipe_shifts)
        }
    }
