# app/routers/shift_template.py
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from sqlmodel import Session
from typing import List

from app.core.security import get_current_user
from app.db.session import get_session
from app.utils.organization_lookup import get_org_by_slug

from app.services.shift_template_service import ShiftTemplateService
from app.schemas import (
    ShiftTemplateCreate,
    ShiftTemplateUpdate,
    ShiftTemplateRead,
    ShiftTemplateApply,
    ShiftTemplateFromHistory
)


router = APIRouter(prefix="/{org_slug}/shift-templates", tags=["Shift Templates"])
security = HTTPBearer()


# ---------------------------------------------------------
# CREATE TEMPLATE
# ---------------------------------------------------------
@router.post("", response_model=ShiftTemplateRead, dependencies=[Security(security)])
def create_template(
    org_slug: str,
    payload: ShiftTemplateCreate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Create a new shift template.
    
    Only MANAGER and ADMIN roles can create templates.
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden: Only managers and admins can create templates")
    
    # Get employee_id from token (optional for ADMIN users)
    employee_id = current.get("employee_id")
    
    # MANAGER users must have employee_id, but ADMIN users don't need it
    if current.get("role") == "MANAGER" and not employee_id:
        raise HTTPException(400, "Employee ID not found in token. Please ensure your account is linked to a staff record.")
    
    org = get_org_by_slug(org_slug, session)
    
    try:
        template = ShiftTemplateService.create(
            session,
            org.id,
            employee_id,  # Can be None for ADMIN
            payload
        )
        return template
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# LIST TEMPLATES
# ---------------------------------------------------------
@router.get("", response_model=List[ShiftTemplateRead], dependencies=[Security(security)])
def list_templates(
    org_slug: str,
    active_only: bool = True,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    List all shift templates for the organization.
    
    Query Parameters:
    - active_only: If true, only return active templates (default: true)
    """
    org = get_org_by_slug(org_slug, session)
    
    templates = ShiftTemplateService.list_by_org(session, org.id, active_only)
    return templates


# ---------------------------------------------------------
# GET SINGLE TEMPLATE
# ---------------------------------------------------------
@router.get("/{template_id}", response_model=ShiftTemplateRead, dependencies=[Security(security)])
def get_template(
    org_slug: str,
    template_id: int,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """Get a single template by ID"""
    org = get_org_by_slug(org_slug, session)
    
    template = ShiftTemplateService.get(session, template_id, org.id)
    if not template:
        raise HTTPException(404, "Template not found")
    
    return template


# ---------------------------------------------------------
# UPDATE TEMPLATE
# ---------------------------------------------------------
@router.put("/{template_id}", response_model=ShiftTemplateRead, dependencies=[Security(security)])
def update_template(
    org_slug: str,
    template_id: int,
    payload: ShiftTemplateUpdate,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Update an existing template.
    
    Only MANAGER and ADMIN roles can update templates.
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden: Only managers and admins can update templates")
    
    org = get_org_by_slug(org_slug, session)
    
    try:
        template = ShiftTemplateService.update(session, template_id, org.id, payload)
        if not template:
            raise HTTPException(404, "Template not found")
        return template
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# DELETE TEMPLATE (SOFT DELETE)
# ---------------------------------------------------------
@router.delete("/{template_id}", dependencies=[Security(security)])
def delete_template(
    org_slug: str,
    template_id: int,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Delete a template (soft delete - sets is_active to false).
    
    Only MANAGER and ADMIN roles can delete templates.
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden: Only managers and admins can delete templates")
    
    org = get_org_by_slug(org_slug, session)
    
    deleted = ShiftTemplateService.delete(session, template_id, org.id)
    if not deleted:
        raise HTTPException(404, "Template not found")
    
    return {"ok": True, "deleted": True}


# ---------------------------------------------------------
# APPLY TEMPLATE
# ---------------------------------------------------------
@router.post("/{template_id}/apply", dependencies=[Security(security)])
def apply_template(
    org_slug: str,
    template_id: int,
    payload: ShiftTemplateApply,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Apply a template to generate shifts for a specified date range.
    
    Only MANAGER and ADMIN roles can apply templates.
    
    Request Body:
    - start_date: Start date for shift generation
    - end_date: End date for shift generation
    - overrides: Optional modifications to template config
    
    Returns:
    - Summary of created shifts
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden: Only managers and admins can apply templates")
    
    org = get_org_by_slug(org_slug, session)
    
    try:
        result = ShiftTemplateService.apply_template(
            session,
            template_id,
            org.id,
            payload.start_date,
            payload.end_date,
            payload.overrides
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------
# CREATE TEMPLATE FROM HISTORY
# ---------------------------------------------------------
@router.post("/from-history", response_model=ShiftTemplateRead, dependencies=[Security(security)])
def create_template_from_history(
    org_slug: str,
    payload: ShiftTemplateFromHistory,
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    Create a template by extracting patterns from historical shift data.
    
    Only MANAGER and ADMIN roles can create templates from history.
    
    Request Body:
    - name: Name for the new template
    - description: Optional description
    - source_start_date: Start date of historical data to analyze
    - source_end_date: End date of historical data to analyze
    - department_id: Optional - filter by specific department
    
    The system will analyze shifts in the date range and extract:
    - Common shift types
    - Average staffing requirements
    - Required skills
    - Priorities and hours
    """
    if current.get("role") not in ("MANAGER", "ADMIN"):
        raise HTTPException(403, "Forbidden: Only managers and admins can create templates")
    
    # Get employee_id from token (optional for ADMIN users)
    employee_id = current.get("employee_id")
    
    # MANAGER users must have employee_id, but ADMIN users don't need it
    if current.get("role") == "MANAGER" and not employee_id:
        raise HTTPException(400, "Employee ID not found in token. Please ensure your account is linked to a staff record.")
    
    org = get_org_by_slug(org_slug, session)
    
    try:
        template = ShiftTemplateService.create_from_history(
            session,
            org.id,
            employee_id,  # Can be None for ADMIN
            payload
        )
        return template
    except ValueError as e:
        raise HTTPException(400, str(e))
