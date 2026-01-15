# app/routers/shift_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session
from datetime import date

from app.core.security import get_current_user
from app.db.session import get_session
from app.utils.organization_lookup import get_org_by_slug

from app.services.shift_service import ShiftService
from app.services.staff_service import StaffService

from app.schemas import ShiftCreate, ShiftRead


router = APIRouter(prefix="/{org_slug}/shifts", tags=["Shifts"])
security = HTTPBearer()


# ---------------------------------------------------------
# CREATE SHIFT
# ---------------------------------------------------------
@router.post("", response_model=ShiftRead, dependencies=[Security(security)])
def create_shift(
    org_slug: str,
    payload: ShiftCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):

    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)

    try:
        shift = ShiftService.create(session, org.id, payload)
        # Create response with serialized required skills
        response_data = {
            "id": shift.id,
            "shift_date": shift.shift_date,
            "shift_type": shift.shift_type,
            "department_id": shift.department_id,
            "min_staff": shift.min_staff,
            "max_staff": shift.max_staff,
            "priority": shift.priority,
            "requires_supervisor": shift.requires_supervisor,
            "hours": shift.hours,
            "required_skills": ShiftService.serialize_required_skills(shift)
        }
        return response_data
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# LIST SHIFTS
# ---------------------------------------------------------
@router.get("", dependencies=[Security(security)])
def list_shifts(
    org_slug: str,
    start_date: str = None,
    end_date: str = None,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):

    org = get_org_by_slug(org_slug, session)

    if current.get("role") == "STAFF":
        # Staff only sees shifts assigned to them - use ORM instead of raw SQL
        from sqlmodel import select
        from app.db.models import Shift, ShiftAssignment
        
        # Get total count
        total_stmt = select(func.count(Shift.id)).join(ShiftAssignment).where(
            ShiftAssignment.employee_id == current["employee_id"]
        )
        total = session.exec(total_stmt).one()
        
        # Get paginated shifts
        stmt = select(Shift).join(ShiftAssignment).where(
            ShiftAssignment.employee_id == current["employee_id"]
        ).offset(skip).limit(limit)
        shifts = session.exec(stmt).all()

        # serialize required skills
        serialized_shifts = []
        for sh in shifts:
            shift_data = {
                "id": sh.id,
                "shift_date": sh.shift_date,
                "shift_type": sh.shift_type,
                "department_id": sh.department_id,
                "min_staff": sh.min_staff,
                "max_staff": sh.max_staff,
                "priority": sh.priority,
                "requires_supervisor": sh.requires_supervisor,
                "hours": sh.hours,
                "required_skills": ShiftService.serialize_required_skills(sh)
            }
            serialized_shifts.append(shift_data)
        
        return {
            "ok": True,
            "data": serialized_shifts,
            "pagination": {
                "total": total,
                "skip": skip,
                "limit": limit,
                "has_more": (skip + len(serialized_shifts)) < total
            }
        }

    # Manager / Admin
    from sqlmodel import func
    s = date.fromisoformat(start_date) if start_date else None
    e = date.fromisoformat(end_date) if end_date else None

    # Get total count
    total = ShiftService.count_by_org(session, org.id, s, e)
    
    # Get paginated shifts
    shifts = ShiftService.list_by_org(session, org.id, s, e, skip=skip, limit=limit)
    serialized_shifts = []
    for sh in shifts:
        shift_data = {
            "id": sh.id,
            "shift_date": sh.shift_date,
            "shift_type": sh.shift_type,
            "department_id": sh.department_id,
            "min_staff": sh.min_staff,
            "max_staff": sh.max_staff,
            "priority": sh.priority,
            "requires_supervisor": sh.requires_supervisor,
            "hours": sh.hours,
            "required_skills": ShiftService.serialize_required_skills(sh)
        }
        serialized_shifts.append(shift_data)

    return {
        "ok": True,
        "data": serialized_shifts,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(serialized_shifts)) < total
        }
    }


# ---------------------------------------------------------
# GET SINGLE SHIFT
# ---------------------------------------------------------
@router.get("/{shift_id}", response_model=ShiftRead, dependencies=[Security(security)])
def get_shift(
    org_slug: str,
    shift_id: int,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):

    shift = ShiftService.get(session, shift_id)
    if not shift:
        raise HTTPException(404, "Shift not found")

    org = get_org_by_slug(org_slug, session)

    if shift.department.org_id != org.id:
        raise HTTPException(403, "Shift not in your organization")

    # Create response with serialized required skills
    response_data = {
        "id": shift.id,
        "shift_date": shift.shift_date,
        "shift_type": shift.shift_type,
        "department_id": shift.department_id,
        "min_staff": shift.min_staff,
        "max_staff": shift.max_staff,
        "priority": shift.priority,
        "requires_supervisor": shift.requires_supervisor,
        "hours": shift.hours,
        "required_skills": ShiftService.serialize_required_skills(shift)
    }
    return response_data


# ---------------------------------------------------------
# UPDATE SHIFT
# ---------------------------------------------------------
@router.put("/{shift_id}", response_model=ShiftRead, dependencies=[Security(security)])
def update_shift(
    org_slug: str,
    shift_id: int,
    payload: ShiftCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):

    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)

    try:
        shift = ShiftService.update(session, shift_id, payload, org.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not shift:
        raise HTTPException(404, "Shift not found")

    # Create response with serialized required skills
    response_data = {
        "id": shift.id,
        "shift_date": shift.shift_date,
        "shift_type": shift.shift_type,
        "department_id": shift.department_id,
        "min_staff": shift.min_staff,
        "max_staff": shift.max_staff,
        "priority": shift.priority,
        "requires_supervisor": shift.requires_supervisor,
        "hours": shift.hours,
        "required_skills": ShiftService.serialize_required_skills(shift)
    }
    return response_data


# ---------------------------------------------------------
# DELETE SHIFTS BY DATE RANGE
# ---------------------------------------------------------
@router.delete("/range", dependencies=[Security(security)])
def delete_shifts_by_range(
    org_slug: str,
    start_date: str,
    end_date: str,
    department_id: int = None,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Delete shifts within a date range, optionally filtered by department.
    Useful for undoing shift generation mistakes.
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)

    try:
        from datetime import date
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

    try:
        result = ShiftService.delete_by_range(session, org.id, start, end, department_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "ok": True,
        "deleted": result["shifts_deleted"],
        "assignments_deleted": result["assignments_deleted"],
        "message": f"Deleted {result['shifts_deleted']} shifts and {result['assignments_deleted']} assignments"
    }


# ---------------------------------------------------------
# DELETE SHIFT
# ---------------------------------------------------------
@router.delete("/{shift_id}", dependencies=[Security(security)])
def delete_shift(
    org_slug: str,
    shift_id: int,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):

    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)

    try:
        deleted = ShiftService.delete(session, shift_id, org.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not deleted:
        raise HTTPException(404, "Shift not found")

    return {"ok": True, "deleted": True}
