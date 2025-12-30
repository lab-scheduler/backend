# app/services/skill_service.py
from sqlmodel import Session
from app.db.models import Skill
from app.schemas import SkillCreate
from app.services.base_service import BaseCRUDService


class SkillServiceCore(BaseCRUDService[Skill]):
    """
    Skill service inheriting standard CRUD from BaseCRUDService.
    """
    
    def __init__(self):
        super().__init__(Skill)
    
    # All CRUD methods inherited from BaseCRUDService


# Convenience instance
_service = SkillServiceCore()


# Static method wrappers for backward compatibility
class SkillService:
    @staticmethod
    def create(session: Session, data: SkillCreate):
        return _service.create(session, data.dict())
    
    @staticmethod
    def list_by_org(session: Session, org_id: int):
        # Note: This requires a join with Department
        # For now, using the old implementation
        from sqlmodel import select
        from app.db.models import Department
        return session.exec(
            select(Skill).join(Department).where(Department.org_id == org_id)
        ).all()
    
    @staticmethod
    def list_all(session: Session):
        return _service.list_all(session, limit=1000)
    
    @staticmethod
    def get(session: Session, skill_id: str):
        return _service.get(session, skill_id)
    
    @staticmethod
    def update(session: Session, skill_id: str, data: SkillCreate):
        return _service.update(session, skill_id, data.dict())
    
    @staticmethod
    def delete(session: Session, skill_id: str):
        return _service.delete(session, skill_id)

