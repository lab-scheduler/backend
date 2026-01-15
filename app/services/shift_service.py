# app/services/shift_service.py
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from datetime import date
from typing import List, Optional

from app.db.models import (
    Shift,
    Department,
    Skill,
    ShiftAssignment,
    ShiftRequiredSkill
)
from app.schemas import ShiftCreate


class ShiftService:

    # ---------------------------------------------------------
    # CREATE SHIFT
    # ---------------------------------------------------------
    @staticmethod
    def create(session: Session, org_id: int, payload: ShiftCreate):
        # Validate department belongs to this org
        dept = session.get(Department, payload.department_id)
        if not dept or dept.org_id != org_id:
            raise ValueError("Department does not belong to this organization")

        # Create shift record
        shift = Shift(
            org_id=org_id,
            shift_date=payload.shift_date,
            shift_type=payload.shift_type,
            department_id=payload.department_id,
            min_staff=payload.min_staff,
            max_staff=payload.max_staff,
            priority=payload.priority,
            requires_supervisor=payload.requires_supervisor,
            hours=payload.hours or 8,
        )

        session.add(shift)
        session.flush()  # Get shift.id without committing to database

        # Add required skills (if any)
        for skill_id in payload.required_skill_ids or []:
            sr = ShiftRequiredSkill(
                shift_id=shift.id,
                skill_id=skill_id
            )
            session.add(sr)

        # Single commit for both shift and required skills
        session.commit()
        session.refresh(shift)
        return shift

    # ---------------------------------------------------------
    # GET SHIFT
    # ---------------------------------------------------------
    @staticmethod
    def get(session: Session, shift_id: int):
        return session.get(Shift, shift_id)

    # ---------------------------------------------------------
    # LIST SHIFTS FOR ORGANIZATION
    # ---------------------------------------------------------
    @staticmethod
    def list_by_org(
        session: Session,
        org_id: int,
        start: Optional[date] = None,
        end: Optional[date] = None,
        skip: int = 0,
        limit: int = 50
    ):
        stmt = (
            select(Shift)
            .join(Department, Shift.department_id == Department.id)
            .where(Department.org_id == org_id)
            .options(
                joinedload(Shift.required_skills).joinedload(ShiftRequiredSkill.skill),
                joinedload(Shift.department),
            )
        )

        if start:
            stmt = stmt.where(Shift.shift_date >= start)
        if end:
            stmt = stmt.where(Shift.shift_date <= end)
        
        # Add pagination
        stmt = stmt.offset(skip).limit(limit)

        # Use unique() to deduplicate results from JOINs
        return session.exec(stmt).unique().all()
    
    @staticmethod
    def count_by_org(
        session: Session,
        org_id: int,
        start: Optional[date] = None,
        end: Optional[date] = None
    ) -> int:
        """Get total count of shifts for pagination"""
        from sqlmodel import func
        stmt = (
            select(func.count(Shift.id))
            .join(Department, Shift.department_id == Department.id)
            .where(Department.org_id == org_id)
        )
        
        if start:
            stmt = stmt.where(Shift.shift_date >= start)
        if end:
            stmt = stmt.where(Shift.shift_date <= end)
        
        return session.exec(stmt).one()

    # ---------------------------------------------------------
    # BUILD SERIALIZED REQUIRED SKILLS
    # ---------------------------------------------------------
    @staticmethod
    def serialize_required_skills(shift: Shift):
        return [
            {
                "skill_id": rs.skill_id,
                "skill_name": rs.skill.skill_name,
                "required_certification": rs.skill.required_certification,
            }
            for rs in shift.required_skills
        ]

    # ---------------------------------------------------------
    # UPDATE SHIFT
    # ---------------------------------------------------------
    @staticmethod
    def update(
        session: Session,
        shift_id: int,
        payload: ShiftCreate,
        org_id: int
    ):
        shift = session.get(Shift, shift_id)
        if not shift:
            return None

        dept = session.get(Department, payload.department_id)
        if not dept or dept.org_id != org_id:
            raise ValueError("Department does not belong to organization")

        # Update fields
        shift.shift_date = payload.shift_date
        shift.shift_type = payload.shift_type
        shift.department_id = payload.department_id
        shift.min_staff = payload.min_staff
        shift.max_staff = payload.max_staff
        shift.priority = payload.priority
        shift.requires_supervisor = payload.requires_supervisor
        shift.hours = payload.hours or 8

        # Replace required skills
        session.query(ShiftRequiredSkill).filter(
            ShiftRequiredSkill.shift_id == shift.id
        ).delete()

        for skill_id in payload.required_skill_ids or []:
            session.add(
                ShiftRequiredSkill(
                    shift_id=shift.id,
                    skill_id=skill_id
                )
            )

        session.add(shift)
        session.commit()
        session.refresh(shift)
        return shift

    # ---------------------------------------------------------
    # DELETE SHIFT
    # ---------------------------------------------------------
    @staticmethod
    def delete(session: Session, shift_id: int, org_id: int):
        shift = session.get(Shift, shift_id)
        if not shift:
            return False

        # validate department ownership
        dept = session.get(Department, shift.department_id)
        if not dept or dept.org_id != org_id:
            raise ValueError("Shift does not belong to this organization")

        # Delete related required skills + assignments
        session.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift.id
        ).delete()

        session.query(ShiftRequiredSkill).filter(
            ShiftRequiredSkill.shift_id == shift.id
        ).delete()

        session.delete(shift)
        session.commit()
        return True

    # ---------------------------------------------------------
    # DELETE SHIFTS BY DATE RANGE
    # ---------------------------------------------------------
    @staticmethod
    def delete_by_range(
        session: Session,
        org_id: int,
        start_date: date,
        end_date: date,
        department_id: Optional[int] = None
    ):
        """
        Delete all shifts within a date range, optionally filtered by department.
        Returns count of deleted shifts and assignments.
        """
        # Build query to find shifts
        stmt = (
            select(Shift)
            .join(Department, Shift.department_id == Department.id)
            .where(Department.org_id == org_id)
            .where(Shift.shift_date >= start_date)
            .where(Shift.shift_date <= end_date)
        )

        # Add department filter if provided
        if department_id is not None:
            # Validate department belongs to org
            dept = session.get(Department, department_id)
            if not dept or dept.org_id != org_id:
                raise ValueError("Department does not belong to this organization")
            stmt = stmt.where(Shift.department_id == department_id)

        # Get all shifts to delete
        shifts_to_delete = session.exec(stmt).all()
        shift_ids = [shift.id for shift in shifts_to_delete]

        if not shift_ids:
            return {
                "shifts_deleted": 0,
                "assignments_deleted": 0
            }

        # Count assignments before deletion
        from sqlmodel import func
        assignments_count = session.exec(
            select(func.count(ShiftAssignment.id)).where(
                ShiftAssignment.shift_id.in_(shift_ids)
            )
        ).one()

        # Delete related assignments
        session.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id.in_(shift_ids)
        ).delete(synchronize_session=False)

        # Delete related required skills
        session.query(ShiftRequiredSkill).filter(
            ShiftRequiredSkill.shift_id.in_(shift_ids)
        ).delete(synchronize_session=False)

        # Delete shifts
        session.query(Shift).filter(
            Shift.id.in_(shift_ids)
        ).delete(synchronize_session=False)

        session.commit()

        return {
            "shifts_deleted": len(shift_ids),
            "assignments_deleted": assignments_count
        }

