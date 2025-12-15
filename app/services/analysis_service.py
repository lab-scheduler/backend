# app/services/analysis_service.py
from datetime import date
from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.scheduler_engine.core.scoring_engine import ScoringEngine

class AnalysisService:

    @staticmethod
    def analyze_range(session, org_id: int, start: date, end: date):
        adapter = DBAdapter(session, org_id)
        staff = adapter.load_staff()
        shifts = adapter.load_shifts(start, end)
        # build a mini-engine for analysis
        from app.scheduler_engine.core.greedy_engine import GreedyEngine
        engine = GreedyEngine()
        for s in staff:
            engine.add_staff(s)
        for sh in shifts:
            engine.add_shift(sh)
        scorer = ScoringEngine()
        summary = scorer.analyze_schedule(engine)
        # return detailed metrics sample
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
