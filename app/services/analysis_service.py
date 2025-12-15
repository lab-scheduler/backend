# app/services/analysis_service.py
from datetime import date
from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.scheduler_engine.core.scoring_engine import ScoringEngine

class AnalysisService:

    @staticmethod
    def analyze_range(session, org_id: int, start: date, end: date):
        # Use optimized adapter for better performance
        adapter = DBAdapter(session, org_id)

        # Use fast aggregate queries instead of building full engine
        stats = adapter.get_coverage_stats_fast(start, end)

        # Return summary in expected format
        summary = {
            "total_shifts": stats["total_shifts"],
            "covered": stats["covered_shifts"],
            "coverage_rate": stats["coverage_rate"],
            "total_assignments": stats["total_assignments"],
            "unique_staff": stats["unique_staff"]
        }

        return {"ok": True, "summary": summary}

    @staticmethod
    def analyze_for_staff(session, org_id: int, staff_id: str, start: date, end: date):
        adapter = DBAdapter(session, org_id)
        staff = adapter.load_staff()
        shifts = adapter.load_shifts(start, end)
        # filter shifts assigned to staff
        assigned = [sh for sh in shifts if staff_id in sh.assigned_staff_ids]
        rec = []
        if len(assigned) > 5:
            rec.append("Consider reducing consecutive shifts for fatigue")
        return {"ok": True, "staff_id": staff_id, "total_shifts": len(assigned), "recommendations": rec}

    @staticmethod
    def analyze_for_department(session, org_id: int, dept_id: int, start: date, end: date):
        adapter = DBAdapter(session, org_id)
        shifts = adapter.load_shifts(start, end)
        dept_shifts = [sh for sh in shifts if sh.department_id == dept_id]
        covered = sum(1 for s in dept_shifts if len(s.assigned_staff_ids) >= s.min_staff)
        total = len(dept_shifts)
        coverage_rate = (covered/total*100) if total else 100
        return {"ok": True, "department_id": dept_id, "total_shifts": total, "coverage_rate": coverage_rate}
