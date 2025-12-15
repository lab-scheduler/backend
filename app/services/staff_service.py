# app/services/staff_service.py
from sqlmodel import Session, select
from app.db.models import Staff
from app.schemas import StaffCreate, StaffUpdate
from datetime import datetime

class StaffService:

    @staticmethod
    def create_staff(session: Session, data: StaffCreate):
        staff = Staff(**data.dict())
        staff.created_at = datetime.utcnow()
        session.add(staff)
        session.commit()
        session.refresh(staff)
        return staff

    @staticmethod
    def list_staff(session: Session, org_id: int):
        return session.exec(select(Staff).where(Staff.org_id == org_id)).all()

    @staticmethod
    def get_staff(session: Session, employee_id: str):
        return session.get(Staff, employee_id)

    @staticmethod
    def update_staff(session: Session, employee_id: str, data: StaffUpdate):
        staff = session.get(Staff, employee_id)
        if not staff:
            return None
        for k, v in data.dict(exclude_unset=True).items():
            setattr(staff, k, v)
        staff.updated_at = datetime.utcnow()
        session.add(staff)
        session.commit()
        session.refresh(staff)
        return staff

    @staticmethod
    def delete_staff(session: Session, employee_id: str):
        staff = session.get(Staff, employee_id)
        if not staff:
            return False
        session.delete(staff)
        session.commit()
        return True
