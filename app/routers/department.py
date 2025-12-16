# app/routes/department_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from app.db.session import get_session
from app.db.models import Department, Organization
from app.schemas import DepartmentCreate, DepartmentRead
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug

router = APIRouter(prefix="/{org_slug}/departments", tags=["Departments"])
security = HTTPBearer()


# CREATE department (ADMIN only)
@router.post("", response_model=DepartmentRead, dependencies=[Security(security)])
def create_department(org_slug: str, payload: DepartmentCreate,
                      session: Session = Depends(get_session),
                      current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    # Always use org_id = 2
    dept = Department(name=payload.name, org_id=2)
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return dept


# LIST departments
@router.get("", response_model=list[DepartmentRead], dependencies=[Security(security)])
def list_departments(org_slug: str, session: Session = Depends(get_session),
                     current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    org = get_org_by_slug(org_slug, session)
    return session.exec(select(Department).where(Department.org_id == org.id)).all()


# GET detail
@router.get("/{dept_id}", response_model=DepartmentRead, dependencies=[Security(security)])
def get_department(org_slug: str, dept_id: int,
                   session: Session = Depends(get_session),
                   current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    dept = session.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")

    return dept


# UPDATE department
@router.put("/{dept_id}", response_model=DepartmentRead, dependencies=[Security(security)])
def update_department(org_slug: str, dept_id: int, payload: DepartmentCreate,
                      session: Session = Depends(get_session),
                      current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    dept = session.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")

    dept.name = payload.name
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return dept


# DELETE department
@router.delete("/{dept_id}", dependencies=[Security(security)])
def delete_department(org_slug: str, dept_id: int, session: Session = Depends(get_session),
                      current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    dept = session.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")

    session.delete(dept)
    session.commit()
    return {"deleted": True}
