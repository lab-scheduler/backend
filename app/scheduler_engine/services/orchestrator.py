# app/scheduler_engine/services/orchestrator.py
from datetime import date
from sqlmodel import select
from typing import Dict, Any
from app.scheduler_engine.core.greedy_engine import GreedyEngine
from app.scheduler_engine.core.cpsat_engine import CpsatEngine, ORTOOLS_AVAILABLE
from app.scheduler_engine.adapters.db_adapter import DBAdapter

from app.db import models as db_models

class SchedulerOrchestrator:
    def __init__(self, session, org_id: int):
        self.session = session
        self.org_id = org_id

    def run(self, start: date, end: date, use_cpsat: bool = False, cpsat_time: int = 30) -> Dict[str, Any]:
        adapter = DBAdapter(self.session, self.org_id)

        # 1) load data
        staff = adapter.load_staff()
        shifts = adapter.load_shifts(start, end)
        leaves = adapter.load_leaves(start, end)

        out = {
            "ok": False,
            "meta": {
                "requested_start": start.isoformat(),
                "requested_end": end.isoformat(),
                "staff_count": len(staff),
                "shifts_loaded": len(shifts),
                "leaves_loaded": len(leaves),
            },
            "conflicts": {},
            "shifts": [],
            "cpsat": None,
            "summary": {}
        }

        # 2) quick sanity checks
        if not shifts:
            out["reason"] = "No shifts found in date range"
            out["ok"] = True
            out["summary"] = {"total_shifts": 0, "fully_covered": 0, "coverage_rate": 0}
            return out

        # 3) pending leave check: (any pending leave overlapping)
        pending = [lv for lv in leaves if getattr(lv, "status", "").upper() == "PENDING"]
        if pending:
            out["reason"] = "Pending leave requests exist in period; manager intervention required"
            out["ok"] = False
            out["pending_leaves_count"] = len(pending)
            out["pending_leaves_sample"] = [{"employee_id": p.employee_id, "start": p.start_date.isoformat(), "end": p.end_date.isoformat()} for p in pending[:5]]
            return out

        # 4) instantiate engine & populate
        engine = GreedyEngine()
        for s in staff:
            engine.add_staff(s)
        for sh in shifts:
            engine.add_shift(sh)
        for lv in leaves:
            engine.add_leave(lv)

        # 5) run greedy scheduling (populate assigned_staff_ids on engine shifts)
        conflicts = engine.schedule_date_range(start, end)
        out["conflicts"] = conflicts or {}

        # 6) Collect pre-CPSAT assignment snapshot
        pre_assign_snapshot = [{ "shift_id": sh.id, "assigned_staff": list(sh.assigned_staff_ids) } for sh in shifts]

        # 7) optionally run CPSAT to improve solution
        if use_cpsat:
            if not ORTOOLS_AVAILABLE:
                out["cpsat"] = {"ok": False, "reason": "ortools not installed"}
            else:
                try:
                    cpsat = CpsatEngine(staff, shifts)
                    ok, cpsat_out = cpsat.optimize(max_time_seconds=cpsat_time)
                    out["cpsat"] = {"ok": ok, "result": cpsat_out}
                    # If CPSAT returned assignments, apply them to engine shifts
                    if ok and cpsat_out.get("assignments"):
                        # reset engine assignments and apply mapping
                        assign_map = {}
                        for a in cpsat_out["assignments"]:
                            assign_map.setdefault(a["shift_id"], []).append(a["employee_id"])
                        for sh in shifts:
                            sh.assigned_staff_ids = assign_map.get(sh.id, sh.assigned_staff_ids)
                except Exception as e:
                    out["cpsat"] = {"ok": False, "error": str(e)}

        # 8) persist assignments to DB and get detailed result
        try:
            persist_result = adapter.persist_assignments(shifts)
            out["persist_result"] = persist_result
        except Exception as e:
            out["ok"] = False
            out["reason"] = f"DB persist failed: {str(e)}"
            return out

        # 9) scoring summary
        summary = engine.scorer.analyze_schedule(engine)
        out["summary"] = summary

        # 10) build detailed shifts payload (DB + staff detail)
        detailed_shifts = []
        for sh_info in out["persist_result"]["shifts"]:
            sh_row = self.session.get(db_models.Shift, sh_info["shift_id"])
            # gather assignments with staff meta
            assignment_rows = self.session.exec(select(db_models.ShiftAssignment).where(db_models.ShiftAssignment.shift_id == sh_row.id)).all()
            assigned_staff = []
            for a in assignment_rows:
                staff_row = self.session.get(db_models.Staff, a.employee_id)
                if staff_row:
                    assigned_staff.append({
                        "employee_id": staff_row.employee_id,
                        "full_name": getattr(staff_row, "full_name", None),
                        "is_supervisor": getattr(staff_row, "is_supervisor", False),
                    })
            detailed_shifts.append({
                "shift_id": sh_row.id,
                "shift_date": getattr(sh_row, "shift_date", None).isoformat(),
                "department_id": getattr(sh_row, "department_id", None),
                "min_staff": getattr(sh_row, "min_staff", None),
                "max_staff": getattr(sh_row, "max_staff", None),
                "assigned": assigned_staff
            })

        out["shifts"] = detailed_shifts
        out["ok"] = True
        return out
