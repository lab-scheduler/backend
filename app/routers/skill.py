# app/routes/skill_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from app.db.session import get_session
from app.db.models import Skill, Department
from app.schemas import SkillCreate, SkillRead
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug

router = APIRouter(prefix="/{org_slug}/skills", tags=["Skills"])
security = HTTPBearer()


def _validate_manager_skill_scope(session: Session, current: dict, dept_id: int):
    """
    Manager must only manage skills inside departments of their own org.
    Admin bypasses this.
    """
    if current.get("role") == "ADMIN":
        return

    if current.get("role") != "MANAGER":
        raise HTTPException(403, "Forbidden")

    dept = session.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")

    if dept.org_id != current.get("org_id"):
        raise HTTPException(403, "Managers can only manage skills for departments in their own organization")


# CREATE skill
@router.post("", response_model=SkillRead, dependencies=[Security(security)])
def create_skill(org_slug: str, payload: SkillCreate, session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)

    # Validate manager scope
    _validate_manager_skill_scope(session, current, payload.department_id)

    skill = Skill(**payload.dict())
    session.add(skill)
    session.commit()
    session.refresh(skill)
    return skill


# LIST skills (ADMIN + MANAGER same org)
@router.get("", response_model=list[SkillRead], dependencies=[Security(security)])
def list_skills(org_slug: str, session: Session = Depends(get_session),
                current: dict = Depends(get_current_user)):

    org = get_org_by_slug(org_slug, session)

    role = current.get("role")
    if role == "ADMIN":
        return session.exec(select(Skill)).all()

    if role == "MANAGER":
        return session.exec(
            select(Skill).join(Department).where(Department.org_id == org.id)
        ).all()

    raise HTTPException(403, "Forbidden")


# UPDATE skill
@router.put("/{skill_id}", response_model=SkillRead, dependencies=[Security(security)])
def update_skill(org_slug: str, skill_id: int, payload: SkillCreate,
                 session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):

    skill = session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")

    _validate_manager_skill_scope(session, current, skill.department_id)

    skill.skill_name = payload.skill_name
    skill.required_certification = payload.required_certification

    session.add(skill)
    session.commit()
    session.refresh(skill)
    return skill


# DELETE skill
@router.delete("/{skill_id}", dependencies=[Security(security)])
def delete_skill(org_slug: str, skill_id: int, session: Session = Depends(get_session),
                 current: dict = Depends(get_current_user)):

    skill = session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")

    _validate_manager_skill_scope(session, current, skill.department_id)

    session.delete(skill)
    session.commit()
    return {"deleted": True}
