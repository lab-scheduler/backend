# app/routes/organization_routes.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from app.db.session import get_session
from app.db.models import Organization
from app.schemas import OrganizationCreate, OrganizationRead
from app.core.security import get_current_user

router = APIRouter(prefix="/organizations", tags=["Organizations"])
security = HTTPBearer()


# CREATE (ADMIN only)
@router.post("", response_model=OrganizationRead, dependencies=[Security(security)])
def create_org(payload: OrganizationCreate, session: Session = Depends(get_session),
               current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    # create slug automatically
    slug = payload.name.lower().replace(" ", "-")

    org = Organization(
        name=payload.name,
        address=payload.address,
        slug=slug
    )
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


# LIST (ADMIN only)
@router.get("", response_model=list[OrganizationRead], dependencies=[Security(security)])
def list_orgs(session: Session = Depends(get_session),
              current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    return session.exec(select(Organization)).all()


# GET detail (ADMIN only)
@router.get("/{org_id}", response_model=OrganizationRead, dependencies=[Security(security)])
def get_org(org_id: int, session: Session = Depends(get_session),
            current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    return org


# UPDATE (ADMIN only)
@router.put("/{org_id}", response_model=OrganizationRead, dependencies=[Security(security)])
def update_org(org_id: int, payload: OrganizationCreate, session: Session = Depends(get_session),
               current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    org.name = payload.name
    org.address = payload.address
    org.slug = payload.name.lower().replace(" ", "-")

    session.add(org)
    session.commit()
    session.refresh(org)
    return org


# DELETE (ADMIN only)
@router.delete("/{org_id}", dependencies=[Security(security)])
def delete_org(org_id: int, session: Session = Depends(get_session),
               current: dict = Depends(get_current_user)):

    if current.get("role") != "ADMIN":
        raise HTTPException(403, "Forbidden")

    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    session.delete(org)
    session.commit()
    return {"deleted": True}
