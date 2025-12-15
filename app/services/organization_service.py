# app/services/organization_service.py
from sqlmodel import Session, select
from app.db.models import Organization
from app.schemas import OrganizationCreate
from datetime import datetime


class OrganizationService:

    @staticmethod
    def create(session: Session, data: OrganizationCreate):
        slug = data.name.lower().replace(" ", "-")
        org = Organization(
            name=data.name,
            address=data.address,
            slug=slug
        )
        session.add(org)
        session.commit()
        session.refresh(org)
        return org

    @staticmethod
    def list(session: Session):
        return session.exec(select(Organization)).all()

    @staticmethod
    def get(session: Session, org_id: int):
        return session.get(Organization, org_id)

    @staticmethod
    def update(session: Session, org_id: int, data: OrganizationCreate):
        org = session.get(Organization, org_id)
        if not org:
            return None
        
        org.name = data.name
        org.address = data.address
        org.slug = data.name.lower().replace(" ", "-")

        session.add(org)
        session.commit()
        session.refresh(org)
        return org

    @staticmethod
    def delete(session: Session, org_id: int):
        org = session.get(Organization, org_id)
        if not org:
            return False

        session.delete(org)
        session.commit()
        return True
