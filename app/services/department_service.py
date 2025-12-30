# app/services/department_service.py
from sqlmodel import Session
from app.db.models import Department
from app.schemas import DepartmentCreate
from app.services.base_service import BaseCRUDService


class DepartmentServiceCore(BaseCRUDService[Department]):
    """
    Department service inheriting standard CRUD from BaseCRUDService.
    """
    
    def __init__(self):
        super().__init__(Department)
    
    # All CRUD methods inherited from BaseCRUDService:
    # - create(session, data) -> Department
    # - get(session, id) -> Optional[Department]
    # - list_by(session, skip=0, limit=100, **filters) -> List[Department]
    # - update(session, id, data) -> Optional[Department]
    # - delete(session, id) -> bool


# Convenience instance
_service = DepartmentServiceCore()


# Static method wrappers for backward compatibility
class DepartmentService:
    @staticmethod
    def create(session: Session, data: DepartmentCreate):
        return _service.create(session, data.dict())
    
    @staticmethod
    def list(session: Session, org_id: int):
        return _service.list_by(session, org_id=org_id, limit=1000)
    
    @staticmethod
    def get(session: Session, dept_id: int):
        return _service.get(session, dept_id)
    
    @staticmethod
    def update(session: Session, dept_id: int, data: DepartmentCreate):
        return _service.update(session, dept_id, data.dict())
    
    @staticmethod
    def delete(session: Session, dept_id: int):
        return _service.delete(session, dept_id)

