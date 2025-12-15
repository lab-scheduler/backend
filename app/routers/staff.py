# app/routes/staff_routes.py
from fastapi import APIRouter, Depends, HTTPException, Path, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from app.db.session import get_session
from app.services.staff_service import StaffService
from app.db.models import Staff
from app.schemas import StaffCreate, StaffUpdate, StaffRead
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug

router = APIRouter(prefix="/{org_slug}/staff", tags=["Staff"])
security = HTTPBearer()

# CREATE staff (MANAGER can create STAFF in same org; ADMIN can create any)
@router.post("", response_model=StaffRead, dependencies=[Security(security)])
def create_staff(org_slug: str, payload: StaffCreate, session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):
    org = get_org_by_slug(org_slug, session)
    # ensure payload.org_id matches org
    payload.org_id = org.id

    role = current.get("role") if current else None
    if role == "ADMIN":
        # ok
        return StaffService.create_staff(session, payload)

    if role == "MANAGER":
        # manager only create STAFF and only in same org
        if payload.role != "STAFF":
            raise HTTPException(403, "Managers may only create STAFF")
        if current.get("org_id") != org.id:
            raise HTTPException(403, "Managers may only create staff within their organization")
        return StaffService.create_staff(session, payload)

    raise HTTPException(403, "Forbidden")


# LIST staff (MANAGER/ADMIN see all in org; STAFF see only themselves)
@router.get("", response_model=list[StaffRead], dependencies=[Security(security)])
def list_staff(org_slug: str, session: Session = Depends(get_session), current: dict = Depends(get_current_user)):
    org = get_org_by_slug(org_slug, session)
    if not current:
        raise HTTPException(401, "Unauthorized")

    role = current.get("role")
    if role == "ADMIN" or (role == "MANAGER" and current.get("org_id") == org.id):
        return StaffService.list_staff(session, org.id)

    # STAFF: only see themselves (if they belong to this org)
    if role == "STAFF":
        # find staff record for this user
        emp_id = current.get("employee_id")
        if not emp_id:
            raise HTTPException(403, "No employee identity")
        staff = StaffService.get_staff(session, emp_id)
        if not staff or staff.org_id != org.id:
            raise HTTPException(403, "Forbidden")
        return [staff]

    raise HTTPException(403, "Forbidden")


# GET staff detail (ADMIN/manager same org can see; STAFF only self)
@router.get("/{employee_id}", response_model=StaffRead, dependencies=[Security(security)])
def get_staff(org_slug: str, employee_id: str = Path(...), session: Session = Depends(get_session),
              current: dict = Depends(get_current_user)):
    org = get_org_by_slug(org_slug, session)
    staff = StaffService.get_staff(session, employee_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    role = current.get("role")
    if role == "ADMIN":
        return staff
    if role == "MANAGER":
        if staff.org_id != current.get("org_id"):
            raise HTTPException(403, "Cannot access staff from another org")
        if staff.role != "STAFF":
            raise HTTPException(403, "Managers cannot access other managers/admin")
        return staff
    if role == "STAFF":
        if current.get("employee_id") != employee_id:
            raise HTTPException(403, "Can only view own profile")
        return staff

    raise HTTPException(403, "Forbidden")


# PATCH /staff/me - staff update profile (only allowed fields)
class StaffProfileUpdate(StaffUpdate):
    # restrict fields to only editable personal fields on top of StaffUpdate
    pass

@router.patch("/me", response_model=StaffRead, dependencies=[Security(security)])
def update_me(org_slug: str, payload: StaffProfileUpdate, session: Session = Depends(get_session),
              current: dict = Depends(get_current_user)):
    if not current:
        raise HTTPException(401, "Unauthorized")
    if current.get("role") != "STAFF":
        raise HTTPException(403, "Only staff may use this endpoint")

    emp_id = current.get("employee_id")
    if not emp_id:
        raise HTTPException(400, "No employee id in token")

    # limit allowed fields: prevent changing role, org_id, is_supervisor, employee_id
    disallowed = {"role", "org_id", "is_supervisor", "employee_id", "max_hours_per_week"}
    for k in payload.dict(exclude_unset=True).keys():
        if k in disallowed:
            raise HTTPException(403, f"Field {k} cannot be modified by staff")

    updated = StaffService.update_staff(session, emp_id, payload)
    if not updated:
        raise HTTPException(404, "Staff not found")
    return updated


# UPDATE staff (ADMIN or MANAGER managing target)
@router.put("/{employee_id}", response_model=StaffRead, dependencies=[Security(security)])
def update_staff(org_slug: str, employee_id: str, payload: StaffUpdate, session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):
    org = get_org_by_slug(org_slug, session)
    staff = StaffService.get_staff(session, employee_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    # Admin can update everything; Manager limited
    if current.get("role") == "ADMIN":
        return StaffService.update_staff(session, employee_id, payload)

    if current.get("role") == "MANAGER":
        # ensure same org
        if staff.org_id != current.get("org_id") or current.get("org_id") != org.id:
            raise HTTPException(403, "Cannot modify staff outside your organization")
        if staff.role != "STAFF":
            raise HTTPException(403, "Managers cannot modify other managers/admin")
        # prevent manager from elevating role
        if payload.role and payload.role != "STAFF":
            raise HTTPException(403, "Managers cannot assign manager/admin role")
        return StaffService.update_staff(session, employee_id, payload)

    raise HTTPException(403, "Forbidden")


# DELETE staff
@router.delete("/{employee_id}", dependencies=[Security(security)])
def delete_staff(org_slug: str, employee_id: str, session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):
    org = get_org_by_slug(org_slug, session)
    staff = StaffService.get_staff(session, employee_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    if current.get("role") == "ADMIN":
        ok = StaffService.delete_staff(session, employee_id)
        return {"deleted": ok}

    if current.get("role") == "MANAGER":
        if staff.org_id != current.get("org_id") or current.get("org_id") != org.id:
            raise HTTPException(403, "Cannot delete staff outside your organization")
        if staff.role != "STAFF":
            raise HTTPException(403, "Managers cannot delete other managers/admin")
        if current.get("employee_id") == employee_id:
            raise HTTPException(403, "Managers cannot delete themselves")
        ok = StaffService.delete_staff(session, employee_id)
        return {"deleted": ok}

    raise HTTPException(403, "Forbidden")
