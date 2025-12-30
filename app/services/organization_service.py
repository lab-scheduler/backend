# app/services/organization_service.py
from sqlmodel import Session
from app.db.models import Organization
from app.schemas import OrganizationCreate
from app.services.base_service import BaseCRUDService
from typing import Dict, Any


class OrganizationService(BaseCRUDService[Organization]):
    """
    Organization service with custom slug generation.
    Inherits standard CRUD operations from BaseCRUDService.
    """
    
    def __init__(self):
        super().__init__(Organization)
    
    def create(self, session: Session, data: OrganizationCreate) -> Organization:
        """Create organization with auto-generated slug"""
        slug = data.name.lower().replace(" ", "-")
        org_data = {
            "name": data.name,
            "address": data.address,
            "slug": slug
        }
        return super().create(session, org_data)
    
    def update(self, session: Session, org_id: int, data: OrganizationCreate) -> Organization:
        """Update organization with auto-generated slug"""
        slug = data.name.lower().replace(" ", "-")
        org_data = {
            "name": data.name,
            "address": data.address,
            "slug": slug
        }
        return super().update(session, org_id, org_data)
    
    # Inherited methods (no need to redefine):
    # - get(session, id) -> Optional[Organization]
    # - list_all(session, skip=0, limit=100) -> List[Organization]
    # - delete(session, id) -> bool
    # - exists(session, id) -> bool


# Convenience instance for backward compatibility
_service = OrganizationService()

# Static method wrappers for existing code compatibility
class OrganizationServiceCompat:
    @staticmethod
    def create(session: Session, data: OrganizationCreate):
        return _service.create(session, data)
    
    @staticmethod
    def list(session: Session):
        return _service.list_all(session)
    
    @staticmethod
    def get(session: Session, org_id: int):
        return _service.get(session, org_id)
    
    @staticmethod
    def update(session: Session, org_id: int, data: OrganizationCreate):
        return _service.update(session, org_id, data)
    
    @staticmethod
    def delete(session: Session, org_id: int):
        return _service.delete(session, org_id)


# Export compatibility layer as default
OrganizationService = OrganizationServiceCompat

