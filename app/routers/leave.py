# app/routers/leave_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session
from app.db.session import get_session
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug

from app.schemas import LeaveCreate, LeaveRead, LeaveStatus
from app.services.leave_service import LeaveService
from app.services.staff_service import StaffService

router = APIRouter(prefix="/{org_slug}/leaves", tags=["Leaves"])
security = HTTPBearer()


# ---------------------------------------------------------
# STAFF SUBMIT LEAVE
# ---------------------------------------------------------
@router.post("", dependencies=[Security(security)])
def submit_leave(
    org_slug: str,
    payload: LeaveCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):
    submitter = current.get("employee_id")
    role = current.get("role")

    # For STAFF and MANAGER: can only submit for themselves
    # For ADMIN: can submit for any employee in the organization
    target_employee_id = payload.employee_id
    org = get_org_by_slug(org_slug, session)

    if role == "ADMIN":
        # ADMIN can submit for anyone, but need to verify target employee exists in org
        target_staff = StaffService.get_staff(session, target_employee_id)
        if not target_staff or target_staff.org_id != org.id:
            raise HTTPException(404, "Target employee not found in organization")
    else:
        # STAFF and MANAGER can only submit leave for themselves
        if not submitter:
            raise HTTPException(403, "Employee identity missing")

        # Check if submitter belongs to organization
        staff = StaffService.get_staff(session, submitter)
        if not staff or staff.org_id != org.id:
            raise HTTPException(403, "You do not belong to this organization")
        
        if target_employee_id != submitter:
            raise HTTPException(403, "You can only submit leave for yourself")

    # Execute creation
    leave_obj, reschedule_result = LeaveService.create(
        session, payload, target_employee_id, org.id
    )

    # Response format - format leave_obj as dict to ensure leave_code is included
    response = {
        "ok": True,
        "data": {
            "id": str(leave_obj.id),
            "leave_code": leave_obj.leave_code,
            "employee_id": leave_obj.employee_id,
            "start_date": leave_obj.start_date.isoformat(),
            "end_date": leave_obj.end_date.isoformat(),
            "leave_type": leave_obj.leave_type,
            "status": leave_obj.status,
            "reason": leave_obj.reason,
            "submitted_at": leave_obj.created_at.isoformat() if leave_obj.created_at else None,
            "approved_by": leave_obj.approved_by,
            "approved_at": leave_obj.approved_at.isoformat() if leave_obj.approved_at else None
        },
        "auto_reschedule": reschedule_result,
    }

    if leave_obj.status == LeaveStatus.APPROVED:
        response["notification"] = {
            "message": "Auto-approved leave processed. Coverage adjusted (mock)."
        }

    return response


# ---------------------------------------------------------
# STAFF POLL LEAVE BY CODE
# ---------------------------------------------------------
@router.get("/code/{leave_code}", response_model=LeaveRead, dependencies=[Security(security)])
def poll_leave(org_slug: str, leave_code: str,
               session: Session = Depends(get_session),
               current: dict = Depends(get_current_user)):

    lr = LeaveService.get_by_code(session, leave_code)
    if not lr:
        raise HTTPException(404, "Leave code not found")

    org = get_org_by_slug(org_slug, session)
    staff = StaffService.get_staff(session, lr.employee_id)

    # STAFF can only view their own leave
    if current.get("role") == "STAFF" and lr.employee_id != current.get("employee_id"):
        raise HTTPException(403, "Not your leave request")

    if staff.org_id != org.id:
        raise HTTPException(403, "Leave belongs to different organization")

    return lr


# ---------------------------------------------------------
# MANAGER/ADMIN: GET ALL LEAVES
# ---------------------------------------------------------
@router.get("", dependencies=[Security(security)])
def list_leaves(org_slug: str,
                session: Session = Depends(get_session),
                current: dict = Depends(get_current_user)):
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)
    leaves = LeaveService.list_by_org(session, org.id)

    # Convert LeaveRequest objects to dict to ensure all fields are included
    leaves_data = []
    for leave in leaves:
        leaves_data.append({
            "id": str(leave.id),
            "leave_code": leave.leave_code,
            "employee_id": leave.employee_id,
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "reason": leave.reason,
            "submitted_at": leave.created_at.isoformat() if leave.created_at else None,
            "approved_by": leave.approved_by,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None
        })

    return {
        "ok": True,
        "data": leaves_data
    }


# ---------------------------------------------------------
# MANAGER/ADMIN: FILTER BY STATUS
# ---------------------------------------------------------
@router.get("/{status}", dependencies=[Security(security)])
def list_by_status(org_slug: str, status: LeaveStatus,
                   session: Session = Depends(get_session),
                   current: dict = Depends(get_current_user)):

    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)
    result = LeaveService.list_by_status(session, org.id, status)

    # Convert LeaveRequest objects to dict to ensure all fields are included
    leaves_data = []
    for leave in result:
        leaves_data.append({
            "id": str(leave.id),
            "leave_code": leave.leave_code,
            "employee_id": leave.employee_id,
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "reason": leave.reason,
            "submitted_at": leave.created_at.isoformat() if leave.created_at else None,
            "approved_by": leave.approved_by,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None
        })

    return {
        "ok": True,
        "status": status,
        "data": leaves_data,
    }


# ---------------------------------------------------------
# MANAGER/ADMIN: APPROVE/REJECT LEAVE
# ---------------------------------------------------------
@router.post("/{leave_code}/review", dependencies=[Security(security)])
def review_leave(org_slug: str, leave_code: str, payload: dict,
                 session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):

    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)
    lr = LeaveService.get_by_code(session, leave_code)

    if not lr:
        raise HTTPException(404, "Leave not found")

    leave_id = lr.id
    staff = StaffService.get_staff(session, lr.employee_id)
    if staff.org_id != org.id:
        raise HTTPException(403, "Leave belongs to other organization")

    action = payload.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(400, "Invalid action")

    new_status = LeaveStatus.APPROVED if action == "approve" else LeaveStatus.REJECTED

    updated = LeaveService.update_status(
        session,
        leave_id,
        new_status,
        approver=current.get("employee_id"),
    )

    # If approved, remove staff from shift assignments during leave period
    if new_status == LeaveStatus.APPROVED and lr:
        # Get all shift assignments for this staff within the leave dates
        from sqlmodel import select
        from app.db.models import ShiftAssignment, Shift

        # Find shifts during the leave period
        shifts_query = select(Shift).where(
            Shift.shift_date >= lr.start_date,
            Shift.shift_date <= lr.end_date
        )
        shifts_in_leave_period = session.exec(shifts_query).all()

        # Remove assignments for this staff from those shifts
        removed_count = 0
        for shift in shifts_in_leave_period:
            assignments_query = select(ShiftAssignment).where(
                ShiftAssignment.shift_id == shift.id,
                ShiftAssignment.employee_id == lr.employee_id
            )
            assignments = session.exec(assignments_query).all()

            for assignment in assignments:
                session.delete(assignment)
                removed_count += 1

        if removed_count > 0:
            session.commit()

    response = {
        "ok": True,
        "new_status": updated.status,
        "data": {
            "id": str(updated.id),
            "leave_code": updated.leave_code,
            "employee_id": updated.employee_id,
            "start_date": updated.start_date.isoformat(),
            "end_date": updated.end_date.isoformat(),
            "leave_type": updated.leave_type,
            "status": updated.status,
            "reason": updated.reason,
            "submitted_at": updated.created_at.isoformat() if updated.created_at else None,
            "approved_by": updated.approved_by,
            "approved_at": updated.approved_at.isoformat() if updated.approved_at else None
        }
    }

    if new_status == LeaveStatus.APPROVED and lr and 'removed_count' in locals() and removed_count > 0:
        response["message"] = f"Staff removed from {removed_count} shift assignments during leave period"

    return response
