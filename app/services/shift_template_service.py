# app/services/shift_template_service.py
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from collections import defaultdict

from app.db.models import (
    ShiftTemplate,
    Shift,
    ShiftRequiredSkill,
    Department,
    Staff
)
from app.schemas import (
    ShiftTemplateCreate,
    ShiftTemplateUpdate,
    ShiftTemplateFromHistory
)


class ShiftTemplateService:
    """Service for managing shift templates"""

    # ---------------------------------------------------------
    # CREATE TEMPLATE
    # ---------------------------------------------------------
    @staticmethod
    def create(
        session: Session,
        org_id: int,
        employee_id: Optional[str],
        payload: ShiftTemplateCreate
    ) -> ShiftTemplate:
        """Create a new shift template"""
        
        # Validate that creator exists and belongs to org (if employee_id provided)
        if employee_id:
            creator = session.get(Staff, employee_id)
            if not creator or creator.org_id != org_id:
                raise ValueError("Creator does not belong to this organization")
        
        # Validate config structure
        if not isinstance(payload.config, dict):
            raise ValueError("Config must be a dictionary")
        
        if "departments" not in payload.config and "pipelines" not in payload.config:
            raise ValueError("Config must contain 'departments' or 'pipelines'")
        
        template = ShiftTemplate(
            org_id=org_id,
            name=payload.name,
            description=payload.description,
            created_by=employee_id,  # Can be None for ADMIN users
            config=payload.config,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        session.commit()
        session.refresh(template)
        return template

    # ---------------------------------------------------------
    # GET TEMPLATE
    # ---------------------------------------------------------
    @staticmethod
    def get(session: Session, template_id: int, org_id: int) -> Optional[ShiftTemplate]:
        """Get a single template by ID"""
        template = session.get(ShiftTemplate, template_id)
        if not template or template.org_id != org_id:
            return None
        return template

    # ---------------------------------------------------------
    # LIST TEMPLATES
    # ---------------------------------------------------------
    @staticmethod
    def list_by_org(
        session: Session,
        org_id: int,
        active_only: bool = True
    ) -> List[ShiftTemplate]:
        """List all templates for an organization"""
        stmt = select(ShiftTemplate).where(ShiftTemplate.org_id == org_id)
        
        if active_only:
            stmt = stmt.where(ShiftTemplate.is_active == True)
        
        stmt = stmt.order_by(ShiftTemplate.use_count.desc(), ShiftTemplate.name)
        
        return session.exec(stmt).all()

    # ---------------------------------------------------------
    # UPDATE TEMPLATE
    # ---------------------------------------------------------
    @staticmethod
    def update(
        session: Session,
        template_id: int,
        org_id: int,
        payload: ShiftTemplateUpdate
    ) -> Optional[ShiftTemplate]:
        """Update an existing template"""
        template = ShiftTemplateService.get(session, template_id, org_id)
        if not template:
            return None
        
        # Update fields if provided
        if payload.name is not None:
            template.name = payload.name
        if payload.description is not None:
            template.description = payload.description
        if payload.config is not None:
            template.config = payload.config
        if payload.is_active is not None:
            template.is_active = payload.is_active
        
        template.updated_at = datetime.utcnow()
        
        session.add(template)
        session.commit()
        session.refresh(template)
        return template

    # ---------------------------------------------------------
    # DELETE TEMPLATE
    # ---------------------------------------------------------
    @staticmethod
    def delete(session: Session, template_id: int, org_id: int) -> bool:
        """Delete a template (soft delete by setting is_active=False)"""
        template = ShiftTemplateService.get(session, template_id, org_id)
        if not template:
            return False
        
        # Soft delete
        template.is_active = False
        template.updated_at = datetime.utcnow()
        session.add(template)
        session.commit()
        return True

    # ---------------------------------------------------------
    # APPLY TEMPLATE
    # ---------------------------------------------------------
    @staticmethod
    def apply_template(
        session: Session,
        template_id: int,
        org_id: int,
        start_date: date,
        end_date: date,
        overrides: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Apply a template to generate shifts for a date range"""
        template = ShiftTemplateService.get(session, template_id, org_id)
        if not template:
            raise ValueError("Template not found")
        
        # Get config and apply overrides if provided
        config = template.config.copy()
        if overrides:
            # Deep merge overrides into config
            config = ShiftTemplateService._merge_config(config, overrides)
        
        # Validate config has at least one rule
        dept_rules = config.get("departments", [])
        pipeline_rules = config.get("pipelines", [])
        
        if not dept_rules and not pipeline_rules:
            raise ValueError("Template config must contain at least one department or pipeline rule")
        
        # Validate department rules have required fields
        for idx, rule in enumerate(dept_rules):
            if not isinstance(rule, dict):
                raise ValueError(f"Department rule {idx} must be a dictionary")
            if "department_id" not in rule:
                raise ValueError(f"Department rule {idx} is missing required field 'department_id'")
        
        # Use existing shift generator service
        from app.scheduler_engine.services.shift_generator import ShiftGeneratorService
        
        created_dept_shifts = ShiftGeneratorService.generate_dept_shifts(
            session, org_id, dept_rules, start_date, end_date
        )
        
        created_pipe_shifts = ShiftGeneratorService.generate_pipeline_shifts(
            session, org_id, pipeline_rules, start_date, end_date
        )
        
        # Update template usage metadata
        template.use_count += 1
        template.last_used = datetime.utcnow()
        session.add(template)
        session.commit()
        
        return {
            "ok": True,
            "template_id": template.id,
            "template_name": template.name,
            "summary": {
                "department_shifts_created": len(created_dept_shifts),
                "pipeline_shifts_created": len(created_pipe_shifts),
                "total": len(created_dept_shifts) + len(created_pipe_shifts)
            }
        }

    # ---------------------------------------------------------
    # CREATE TEMPLATE FROM HISTORY
    # ---------------------------------------------------------
    @staticmethod
    def create_from_history(
        session: Session,
        org_id: int,
        employee_id: Optional[str],
        payload: ShiftTemplateFromHistory
    ) -> ShiftTemplate:
        """Extract a template from historical shift data"""
        
        # Validate creator (if employee_id provided)
        if employee_id:
            creator = session.get(Staff, employee_id)
            if not creator or creator.org_id != org_id:
                raise ValueError("Creator does not belong to this organization")
        
        # Build query for historical shifts
        stmt = (
            select(Shift)
            .join(Department, Shift.department_id == Department.id)
            .where(
                Department.org_id == org_id,
                Shift.shift_date >= payload.source_start_date,
                Shift.shift_date <= payload.source_end_date
            )
            .options(
                joinedload(Shift.required_skills).joinedload(ShiftRequiredSkill.skill),
                joinedload(Shift.department)
            )
        )
        
        if payload.department_id:
            stmt = stmt.where(Shift.department_id == payload.department_id)
        
        shifts = session.exec(stmt).unique().all()
        
        if not shifts:
            raise ValueError("No shifts found in the specified date range")
        
        # Analyze shift patterns by department
        dept_patterns = defaultdict(lambda: {
            "shift_types": set(),
            "min_staff_values": [],
            "max_staff_values": [],
            "priorities": [],
            "required_skill_ids": set(),
            "hours": []
        })
        
        for shift in shifts:
            dept_id = shift.department_id
            dept_patterns[dept_id]["shift_types"].add(shift.shift_type.value)
            dept_patterns[dept_id]["min_staff_values"].append(shift.min_staff)
            dept_patterns[dept_id]["max_staff_values"].append(shift.max_staff)
            dept_patterns[dept_id]["priorities"].append(shift.priority)
            dept_patterns[dept_id]["hours"].append(shift.hours)
            
            for req_skill in shift.required_skills:
                dept_patterns[dept_id]["required_skill_ids"].add(req_skill.skill_id)
        
        # Build department rules from patterns
        department_rules = []
        for dept_id, pattern in dept_patterns.items():
            # Calculate averages
            avg_min_staff = int(sum(pattern["min_staff_values"]) / len(pattern["min_staff_values"]))
            avg_max_staff = int(sum(pattern["max_staff_values"]) / len(pattern["max_staff_values"]))
            avg_priority = int(sum(pattern["priorities"]) / len(pattern["priorities"]))
            avg_hours = int(sum(pattern["hours"]) / len(pattern["hours"]))
            
            department_rules.append({
                "department_id": dept_id,
                "shift_types": list(pattern["shift_types"]),
                "min_staff": avg_min_staff,
                "max_staff": avg_max_staff,
                "priority": avg_priority,
                "hours": avg_hours,
                "required_skill_ids": list(pattern["required_skill_ids"])
            })
        
        # Create template config
        config = {
            "departments": department_rules,
            "pipelines": []  # Could be extended to extract pipeline patterns
        }
        
        # Create the template
        template = ShiftTemplate(
            org_id=org_id,
            name=payload.name,
            description=payload.description or f"Template extracted from {payload.source_start_date} to {payload.source_end_date}",
            created_by=employee_id,
            config=config,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(template)
        session.commit()
        session.refresh(template)
        return template

    # ---------------------------------------------------------
    # HELPER: MERGE CONFIG
    # ---------------------------------------------------------
    @staticmethod
    def _merge_config(base: Dict, overrides: Dict) -> Dict:
        """Deep merge overrides into base config"""
        result = base.copy()
        for key, value in overrides.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = ShiftTemplateService._merge_config(result[key], value)
            else:
                result[key] = value
        return result
