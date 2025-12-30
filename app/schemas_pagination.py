# app/schemas.py - Pagination schemas
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional

# ... existing schemas ...

# Pagination schemas
class PaginationParams(BaseModel):
    """Query parameters for pagination"""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of items to return")


T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""
    items: List[T]
    total: int = Field(description="Total number of items available")
    skip: int = Field(description="Number of items skipped")
    limit: int = Field(description="Maximum items per page")
    has_more: bool = Field(description="Whether there are more items available")
    
    @classmethod
    def create(cls, items: List[T], total: int, skip: int, limit: int):
        """Helper to create paginated response"""
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + len(items)) < total
        )
