# app/scheduler_engine/adapters/db_adapter.py
from sqlmodel import Session, select
from datetime import date
from typing import List, Dict
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func

from sqlalchemy.exc import SQLAlchemyError

from app.scheduler_engine.adapters.model_mapper import EngineStaff, EngineShift, EngineLeave
from app.db import models as db_models

class DBAdapter:
    def __init__(self, session: Session, org_id: int):
        self.session = session
        self.org_id = org_id

    def load_staff(self) -> List[EngineStaff]:
        """Optimized: Use eager loading to avoid N+1 queries for staff skills"""
        # Load staff with their skills in one query
        stmt = select(db_models.Staff).where(
            db_models.Staff.org_id == self.org_id
        ).options(
            selectinload(db_models.Staff.skills)
        )
        db_rows = self.session.exec(stmt).all()
        engines = []
        for r in db_rows:
            # Now skills are already loaded, no extra query needed
            skills = {ss.skill_id: ss.proficiency_level for ss in r.skills}
            engines.append(EngineStaff(
                employee_id=r.employee_id,
                name=r.full_name,
                org_id=r.org_id,
                max_hours_per_week=r.max_hours_per_week or 40,
                is_supervisor=r.is_supervisor,
                preferred_shifts=getattr(r, "preferred_shifts", []),
                skills=skills,
                role=r.role.value if r.role else "STAFF"
            ))
        return engines

    def load_shifts(self, start: date, end: date) -> List[EngineShift]:
        """Optimized: Use bulk queries to avoid N+1 problems for skills and assignments"""
        # First, get all shifts in the date range
        stmt = select(db_models.Shift).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        )
        db_shifts = self.session.exec(stmt).all()

        if not db_shifts:
            return []

        # Get shift IDs for bulk loading
        shift_ids = [s.id for s in db_shifts]

        # Bulk load required skills for all shifts (1 query instead of N)
        required_skills_stmt = select(db_models.ShiftRequiredSkill).where(
            db_models.ShiftRequiredSkill.shift_id.in_(shift_ids)
        )
        required_skills = self.session.exec(required_skills_stmt).all()

        # Bulk load assignments for all shifts (1 query instead of N)
        assignments_stmt = select(db_models.ShiftAssignment).where(
            db_models.ShiftAssignment.shift_id.in_(shift_ids)
        )
        assignments = self.session.exec(assignments_stmt).all()

        # Group data by shift for quick lookup (O(1) access)
        skills_by_shift = {}
        for rs in required_skills:
            if rs.shift_id not in skills_by_shift:
                skills_by_shift[rs.shift_id] = []
            skills_by_shift[rs.shift_id].append(rs.skill_id)

        assignments_by_shift = {}
        for assignment in assignments:
            if assignment.shift_id not in assignments_by_shift:
                assignments_by_shift[assignment.shift_id] = []
            assignments_by_shift[assignment.shift_id].append(assignment.employee_id)

        # Build EngineShift objects with pre-loaded data
        engines = []
        for s in db_shifts:
            engines.append(EngineShift(
                id=s.id,
                shift_date=s.shift_date,
                shift_type=s.shift_type,
                department_id=s.department_id,
                required_skill_ids=skills_by_shift.get(s.id, []),
                min_staff=s.min_staff,
                max_staff=s.max_staff,
                priority=getattr(s, "priority", 1),
                requires_supervisor=getattr(s, "requires_supervisor", False),
                hours=getattr(s, "hours", 8),
                assigned_staff_ids=assignments_by_shift.get(s.id, [])
            ))
        return engines

    def load_leaves(self, start: date, end: date) -> List[EngineLeave]:
        stmt = select(db_models.LeaveRequest).join(db_models.Staff).where(
            and_(
                db_models.Staff.org_id == self.org_id,
                db_models.LeaveRequest.end_date >= start,
                db_models.LeaveRequest.start_date <= end
            )
        )
        db_leaves = self.session.exec(stmt).all()
        engines = [
            EngineLeave(
                id=l.id,
                employee_id=l.employee_id,
                start_date=l.start_date,
                end_date=l.end_date,
                status=l.status,
                leave_type=l.leave_type
            )
            for l in db_leaves
        ]
        return engines

    def load_assignments_bulk(self, start: date, end: date) -> List[db_models.ShiftAssignment]:
        """Bulk load assignments with shift details in a single query"""
        stmt = select(db_models.ShiftAssignment).join(db_models.Shift).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        ).options(
            selectinload(db_models.ShiftAssignment.shift),
            selectinload(db_models.ShiftAssignment.staff)
        )
        return self.session.exec(stmt).all()

    def get_coverage_stats_fast(self, start: date, end: date) -> Dict:
        """Get coverage statistics using aggregate queries for maximum performance"""
        # Total shifts
        total_shifts_stmt = select(func.count(db_models.Shift.id)).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        )
        total_shifts = self.session.exec(total_shifts_stmt).one()

        # Covered shifts (shifts with at least one assignment)
        covered_shifts_stmt = select(func.count(func.distinct(db_models.ShiftAssignment.shift_id))).join(
            db_models.Shift
        ).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        )
        covered_shifts = self.session.exec(covered_shifts_stmt).one() or 0

        # Total assignments
        total_assignments_stmt = select(func.count(db_models.ShiftAssignment.id)).join(
            db_models.Shift
        ).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        )
        total_assignments = self.session.exec(total_assignments_stmt).one() or 0

        # Unique staff
        unique_staff_stmt = select(func.count(func.distinct(db_models.ShiftAssignment.employee_id))).join(
            db_models.Shift
        ).where(
            and_(
                db_models.Shift.org_id == self.org_id,
                db_models.Shift.shift_date >= start,
                db_models.Shift.shift_date <= end
            )
        )
        unique_staff = self.session.exec(unique_staff_stmt).one() or 0

        coverage_rate = (covered_shifts / total_shifts * 100) if total_shifts > 0 else 100

        return {
            "total_shifts": total_shifts,
            "covered_shifts": covered_shifts,
            "total_assignments": total_assignments,
            "unique_staff": unique_staff,
            "coverage_rate": coverage_rate
        }