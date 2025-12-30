# app/services/base_service.py
"""
Generic CRUD base service to eliminate code duplication across simple services.
Provides standard create, read, update, delete operations for any SQLModel.
"""
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlmodel import Session, select, SQLModel
from sqlalchemy.exc import SQLAlchemyError


T = TypeVar('T', bound=SQLModel)


class BaseCRUDService(Generic[T]):
    """
    Generic CRUD service providing standard database operations.
    
    Usage:
        class OrganizationService(BaseCRUDService[Organization]):
            def __init__(self):
                super().__init__(Organization)
            
            # Override methods as needed
            def create(self, session, data):
                # Add custom logic (e.g., slug generation)
                data['slug'] = generate_slug(data['name'])
                return super().create(session, data)
    """
    
    def __init__(self, model: Type[T]):
        """
        Initialize with the model class.
        
        Args:
            model: SQLModel class to perform CRUD operations on
        """
        self.model = model
    
    def create(self, session: Session, data: Dict[str, Any]) -> T:
        """
        Create a new record.
        
        Args:
            session: Database session
            data: Dictionary of field values
            
        Returns:
            Created model instance
            
        Raises:
            ValueError: If data is invalid
            SQLAlchemyError: If database operation fails
        """
        try:
            obj = self.model(**data)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            session.rollback()
            raise ValueError(f"Failed to create {self.model.__name__}: {str(e)}")
    
    def get(self, session: Session, id: Any) -> Optional[T]:
        """
        Get a record by ID.
        
        Args:
            session: Database session
            id: Primary key value
            
        Returns:
            Model instance or None if not found
        """
        return session.get(self.model, id)
    
    def get_by(self, session: Session, **filters) -> Optional[T]:
        """
        Get a single record matching filters.
        
        Args:
            session: Database session
            **filters: Field name and value pairs
            
        Returns:
            First matching model instance or None
        """
        stmt = select(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        return session.exec(stmt).first()
    
    def list_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[T]:
        """
        List all records with pagination.
        
        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        stmt = select(self.model).offset(skip).limit(limit)
        return session.exec(stmt).all()
    
    def list_by(self, session: Session, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """
        List records matching filters with pagination.
        
        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Field name and value pairs
            
        Returns:
            List of matching model instances
        """
        stmt = select(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.offset(skip).limit(limit)
        return session.exec(stmt).all()
    
    def count(self, session: Session, **filters) -> int:
        """
        Count records matching filters.
        
        Args:
            session: Database session
            **filters: Field name and value pairs
            
        Returns:
            Number of matching records
        """
        from sqlmodel import func
        stmt = select(func.count(self.model.id))
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        return session.exec(stmt).one()
    
    def update(self, session: Session, id: Any, data: Dict[str, Any]) -> Optional[T]:
        """
        Update a record by ID.
        
        Args:
            session: Database session
            id: Primary key value
            data: Dictionary of fields to update
            
        Returns:
            Updated model instance or None if not found
            
        Raises:
            ValueError: If update fails
        """
        obj = self.get(session, id)
        if not obj:
            return None
        
        try:
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            session.rollback()
            raise ValueError(f"Failed to update {self.model.__name__}: {str(e)}")
    
    def delete(self, session: Session, id: Any) -> bool:
        """
        Delete a record by ID.
        
        Args:
            session: Database session
            id: Primary key value
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If delete fails
        """
        obj = self.get(session, id)
        if not obj:
            return False
        
        try:
            session.delete(obj)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            raise ValueError(f"Failed to delete {self.model.__name__}: {str(e)}")
    
    def exists(self, session: Session, id: Any) -> bool:
        """
        Check if a record exists by ID.
        
        Args:
            session: Database session
            id: Primary key value
            
        Returns:
            True if exists, False otherwise
        """
        return self.get(session, id) is not None
