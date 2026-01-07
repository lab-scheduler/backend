from fastapi import HTTPException
from sqlmodel import Session, select
from app.db.models import Organization
import re

def slugify(name: str):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def get_org_by_slug(org_slug: str, session: Session):
    """
    Fetch organization by slug using database-level filtering.
    Uses the indexed slug column for O(1) lookup performance.
    """
    stmt = select(Organization).where(Organization.slug == org_slug)
    org = session.exec(stmt).first()
    
    if not org:
        raise HTTPException(404, f"Organization '{org_slug}' not found")
    
    return org
