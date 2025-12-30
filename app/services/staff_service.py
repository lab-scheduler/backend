# app/services/staff_service.py
from sqlmodel import Session
from app.db.models import Staff
from app.schemas import StaffCreate, StaffUpdate
from app.services.base_service import BaseCRUDService
from datetime import datetime


class StaffServiceCore(BaseCRUDService[Staff]):
    """
    Staff service with custom timestamp handling.
    Inherits standard CRUD from BaseCRUDService.
    """
    
    def __init__(self):
        super().__init__(Staff)
    
    def create(self, session: Session, data: StaffCreate) -> Staff:
        """Create staff with created_at timestamp"""
        staff_data = data.dict()
        staff_data['created_at'] = datetime.utcnow()
        return super().create(session, staff_data)
    
    def update(self, session: Session, employee_id: str, data: StaffUpdate) -> Staff:
        """Update staff with updated_at timestamp"""
        staff_data = data.dict(exclude_unset=True)
        staff_data['updated_at'] = datetime.utcnow()
        return super().update(session, employee_id, staff_data)


# Convenience instance
_service = StaffServiceCore()


# Static method wrappers for backward compatibility
class StaffService:
    @staticmethod
    def create_staff(session: Session, data: StaffCreate):
        return _service.create(session, data)
    
    @staticmethod
    def list_staff(session: Session, org_id: int):
        return _service.list_by(session, org_id=org_id, limit=1000)
    
    @staticmethod
    def get_staff(session: Session, employee_id: str):
        return _service.get(session, employee_id)
    
    @staticmethod
    def update_staff(session: Session, employee_id: str, data: StaffUpdate):
        return _service.update(session, employee_id, data)
    
    @staticmethod
    def delete_staff(session: Session, employee_id: str):
        return _service.delete(session, employee_id)

