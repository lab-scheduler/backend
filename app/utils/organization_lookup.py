from fastapi import HTTPException
from sqlmodel import Session, select
from app.db.models import Organization
import re

def slugify(name: str):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def get_org_by_slug(org_slug: str, session: Session):
    orgs = session.exec(select(Organization)).all()

    for org in orgs:
        if slugify(org.name) == org_slug:
            return org

    raise HTTPException(404, f"Organization '{org_slug}' not found")
