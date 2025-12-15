# app/scheduler_engine/adapters/db_adapter.py
from sqlmodel import Session, select
from datetime import date
from typing import List, Dict

from sqlalchemy.exc import SQLAlchemyError

from app.scheduler_engine.adapters.model_mapper import EngineStaff, EngineShift, EngineLeave
from app.db import models as db_models

class DBAdapter:
    def __init__(self, session: Session, org_id: int):
        self.session = session
        self.org_id = org_id

    def load_staff(self) -> List[EngineStaff]:
        stmt = select(db_models.Staff).where(db_models.Staff.org_id == self.org_id)
        db_rows = self.session.exec(stmt).all()
        engines = []
        for r in db_rows:
            skills = {ss.skill_id: ss.proficiency_level for ss in getattr(r, "skills", [])}
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
        stmt = select(db_models.Shift).where((db_models.Shift.org_id == self.org_id) & (db_models.Shift.shift_date >= start) & (db_models.Shift.shift_date <= end))
        db_shifts = self.session.exec(stmt).all()
        engines = []
        for s in db_shifts:
            required_skill_ids = [rs.skill_id for rs in getattr(s, "required_skills", [])]
            engines.append(EngineShift(
                id=s.id,
                shift_date=s.shift_date,
                shift_type=s.shift_type,
                department_id=s.department_id,
                required_skill_ids=required_skill_ids,
                min_staff=s.min_staff,
                max_staff=s.max_staff,
                priority=getattr(s, "priority", 1),
                requires_supervisor=getattr(s, "requires_supervisor", False),
                hours=getattr(s, "hours", 8),
                assigned_staff_ids=[a.employee_id for a in getattr(s, "assignments", [])]
            ))
        return engines

    def load_leaves(self, start: date, end: date) -> List[EngineLeave]:
        stmt = select(db_models.LeaveRequest).join(db_models.Staff).where((db_models.Staff.org_id == self.org_id) & (db_models.LeaveRequest.end_date >= start) & (db_models.LeaveRequest.start_date <= end))
        db_leaves = self.session.exec(stmt).all()
        engines = [EngineLeave(id=l.id, employee_id=l.employee_id, start_date=l.start_date, end_date=l.end_date, status=l.status, leave_type=l.leave_type) for l in db_leaves]
        return engines

    def persist_assignments(self, engine_shifts: List[EngineShift]) -> Dict:
        """
        Write engine assignments to DB.
        - For each engine shift, ensure DB shift exists.
        - Delete existing assignments for that shift and insert new ones.
        Returns detailed result: counts + per-shift assignment lists.
        """
        result = {"updated_shifts": 0, "updated_assignments": 0, "shifts": []}
        try:
            for eng in engine_shifts:
                db_shift = self.session.get(db_models.Shift, eng.id)
                if not db_shift:
                    # If DB shift missing, skip but report it (this is unusual)
                    result["shifts"].append({
                        "shift_id": eng.id,
                        "status": "missing_db_shift",
                        "assigned_staff": eng.assigned_staff_ids
                    })
                    continue

                # Delete existing assignments for this shift (bulk)
                stmt = select(db_models.ShiftAssignment).where(db_models.ShiftAssignment.shift_id == db_shift.id)
                existing = self.session.exec(stmt).all()
                for ex in existing:
                    self.session.delete(ex)
                self.session.commit()

                inserted = []
                for emp_id in eng.assigned_staff_ids:
                    assign = db_models.ShiftAssignment(
                        shift_id=db_shift.id,
                        employee_id=emp_id,
                        assigned_hours=eng.hours
                    )
                    self.session.add(assign)
                    inserted.append({"employee_id": emp_id, "assigned_hours": eng.hours})

                self.session.commit()
                result["updated_shifts"] += 1
                result["updated_assignments"] += len(inserted)
                result["shifts"].append({
                    "shift_id": db_shift.id,
                    "date": db_shift.shift_date.isoformat() if getattr(db_shift, "shift_date", None) else None,
                    "assigned": inserted
                })

        except SQLAlchemyError as e:
            # Rollback and bubble up
            self.session.rollback()
            raise

        return result