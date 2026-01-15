# app/routers/skill_staff_routes.py

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session
from uuid import UUID

from app.db.session import get_session
from app.db.models import Staff, Skill
from app.schemas import StaffSkillCreate, StaffSkillRead
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug
from app.services.staff_skill_service import StaffSkillService

router = APIRouter(prefix="/{org_slug}/staff-skills", tags=["Staff Skills"])
security = HTTPBearer()


# -------------------------------------------------------------
# Permission Helpers
# -------------------------------------------------------------
def _ensure_allowed_to_manage(session: Session, current: dict, staff: Staff, skill: Skill):
    """
    Permission logic:
    - ADMIN → full access
    - MANAGER → only staff + skill inside manager's org
    - STAFF → cannot modify anything
    """
    role = current.get("role")

    if role == "ADMIN":
        return

    if role == "MANAGER":
        # staff must belong to manager's org
        if staff.org_id != current.get("org_id"):
            raise HTTPException(403, "Managers can only manage staff within their organization")

        # skill's department must belong to same org
        dept = StaffSkillService.get_department_by_skill(session, skill.id)
        if not dept or dept.org_id != current.get("org_id"):
            raise HTTPException(403, "Managers can only manage skills of departments in their own organization")
        return

    raise HTTPException(403, "Forbidden")


# -------------------------------------------------------------
# LIST all staff skill records for organization
# GET /{org_slug}/staff-skills
# -------------------------------------------------------------
@router.get("", response_model=list[StaffSkillRead], dependencies=[Security(security)])
def list_all_staff_skills(
    org_slug: str,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):
    """List all staff-skills for the organization. Only accessible by ADMIN and MANAGER."""
    
    # Only ADMIN and MANAGER can list all
    if current.get("role") not in ["ADMIN", "MANAGER"]:
        raise HTTPException(403, "Forbidden")
    
    org = get_org_by_slug(org_slug, session)
    
    # MANAGER: only see staff-skills from their org
    if current.get("role") == "MANAGER" and current.get("org_id") != org.id:
        raise HTTPException(403, "Managers can only view staff-skills from their organization")
    
    return StaffSkillService.list_by_org(session, org.id)


# -------------------------------------------------------------
# LIST staff skill records
# GET /{org_slug}/staff-skills/{staff_id}
# -------------------------------------------------------------
@router.get("/{staff_id}", response_model=list[StaffSkillRead], dependencies=[Security(security)])
def list_staff_skills(
    org_slug: str,
    staff_id: str,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):

    org = get_org_by_slug(org_slug, session)
    staff = StaffSkillService.get_staff(session, staff_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    # STAFF can only see their own skills
    if current.get("role") == "STAFF" and current.get("employee_id") != staff_id:
        raise HTTPException(403, "Forbidden")

    # MANAGER / ADMIN must ensure org ownership
    if current.get("role") in ["MANAGER", "ADMIN"]:
        if staff.org_id != org.id:
            raise HTTPException(403, "Staff belongs to another organization")

    return StaffSkillService.list_by_staff(session, staff_id)


# -------------------------------------------------------------
# CREATE staff skill
# POST /{org_slug}/staff-skills/{staff_id}
# -------------------------------------------------------------
@router.post("/{staff_id}", response_model=StaffSkillRead, dependencies=[Security(security)])
def create_staff_skill(
    org_slug: str,
    staff_id: str,
    payload: StaffSkillCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):

    org = get_org_by_slug(org_slug, session)

    staff = StaffSkillService.get_staff(session, staff_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    skill = StaffSkillService.get_skill(session, payload.skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")

    # Permission check
    _ensure_allowed_to_manage(session, current, staff, skill)

    # enforce employee_id
    payload.employee_id = staff_id

    return StaffSkillService.create(session, payload)


# -------------------------------------------------------------
# UPDATE staff skill
# PUT /{org_slug}/staff-skills/{staff_id}/{staff_skill_id}
# -------------------------------------------------------------
@router.put("/{staff_id}/{staff_skill_id}", response_model=StaffSkillRead, dependencies=[Security(security)])
def update_staff_skill(
    org_slug: str,
    staff_id: str,
    staff_skill_id: int,
    payload: StaffSkillCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):

    org = get_org_by_slug(org_slug, session)

    staff = StaffSkillService.get_staff(session, staff_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    record = StaffSkillService.get(session, staff_skill_id)
    if not record:
        raise HTTPException(404, "Staff skill not found")

    skill = StaffSkillService.get_skill(session, payload.skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")

    # Permission check
    _ensure_allowed_to_manage(session, current, staff, skill)

    # Preserve correct employee_id
    payload.employee_id = staff_id

    updated = StaffSkillService.update(session, staff_skill_id, payload)
    return updated


# -------------------------------------------------------------
# DELETE staff skill
# DELETE /{org_slug}/staff-skills/{staff_id}/{staff_skill_id}
# -------------------------------------------------------------
@router.delete("/{staff_id}/{staff_skill_id}", dependencies=[Security(security)])
def delete_staff_skill(
    org_slug: str,
    staff_id: str,
    staff_skill_id: int,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user),
):

    org = get_org_by_slug(org_slug, session)

    staff = StaffSkillService.get_staff(session, staff_id)
    if not staff:
        raise HTTPException(404, "Staff not found")

    record = StaffSkillService.get(session, staff_skill_id)
    if not record:
        raise HTTPException(404, "Staff skill not found")

    skill = StaffSkillService.get_skill(session, record.skill_id)

    # Permission check
    _ensure_allowed_to_manage(session, current, staff, skill)

    StaffSkillService.delete(session, staff_skill_id)
    return {"deleted": True}
