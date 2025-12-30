from typing import Tuple, Dict
from datetime import timedelta
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    ORTOOLS_AVAILABLE = False

from app.scheduler_engine.adapters.model_mapper import EngineShift, EngineStaff
from app.scheduler_engine.core.scoring_engine import ScoringEngine

class CpsatEngine:
    def __init__(self, staff_list: list[EngineStaff], shift_list: list[EngineShift]):
        if not ORTOOLS_AVAILABLE:
            raise ImportError("ortools not installed")
        self.staff = staff_list
        self.shifts = shift_list
        self.model = cp_model.CpModel()
        self.variables = {}
        self.solver = cp_model.CpSolver()
        self.scorer = ScoringEngine()
        # build variables
        self._create_variables()

    def _create_variables(self):
        for s in self.staff:
            for sh in self.shifts:
                self.variables[(s.employee_id, sh.id)] = self.model.NewBoolVar(f"x_{s.employee_id}_{sh.id}")

    def _add_constraints(self):
        # coverage
        for sh in self.shifts:
            vars_for_shift = [self.variables[(s.employee_id, sh.id)] for s in self.staff]
            self.model.Add(sum(vars_for_shift) >= sh.min_staff)
            self.model.Add(sum(vars_for_shift) <= sh.max_staff)
        # availability (leaves)
        for s in self.staff:
            for sh in self.shifts:
                if not s.is_available_on(sh.shift_date):
                    self.model.Add(self.variables[(s.employee_id, sh.id)] == 0)
        # weekly hours constraints (simple)
        dates = [sh.shift_date for sh in self.shifts]
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            current = min_date
            while current <= max_date:
                week_start = current - timedelta(days=current.weekday())
                week_end = week_start + timedelta(days=6)
                shifts_in_week = [sh for sh in self.shifts if week_start <= sh.shift_date <= week_end]
                for s in self.staff:
                    # sum(8 * x) <= max_hours
                    expr = sum(8 * self.variables[(s.employee_id, sh.id)] for sh in shifts_in_week)
                    self.model.Add(expr <= s.max_hours_per_week)
                current = week_end + timedelta(days=1)
        # skills constraints (if lacks, force 0)
        for s in self.staff:
            for sh in self.shifts:
                if sh.required_skill_ids:
                    if not all(s.has_skill(skill) for skill in sh.required_skill_ids):
                        self.model.Add(self.variables[(s.employee_id, sh.id)] == 0)
        # supervisor constraints
        for sh in self.shifts:
            if sh.requires_supervisor:
                sup_vars = [self.variables[(s.employee_id, sh.id)] for s in self.staff if s.is_supervisor]
                if sup_vars:
                    self.model.Add(sum(sup_vars) >= 1)

    def _set_objective(self, minimize_cost: bool = False):
        terms = []
        for s in self.staff:
            for sh in self.shifts:
                score = int(self.scorer.score_staff_for_shift(s, sh))
                terms.append(score * self.variables[(s.employee_id, sh.id)])
        self.model.Maximize(sum(terms))

    def optimize(self, max_time_seconds: int = 30) -> Tuple[bool, Dict]:
        self._add_constraints()
        self._set_objective()
        self.solver.parameters.max_time_in_seconds = max_time_seconds
        status = self.solver.Solve(self.model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # apply solution: return mapping
            assignments = []
            for s in self.staff:
                for sh in self.shifts:
                    val = self.solver.Value(self.variables[(s.employee_id, sh.id)])
                    if val == 1:
                        assignments.append({"employee_id": s.employee_id, "shift_id": sh.id})
            stats = {
                "objective_value": getattr(self.solver, "ObjectiveValue", lambda: None)(),
                "status": self.solver.StatusName(status),
            }
            return True, {"assignments": assignments, "stats": stats}
        else:
            return False, {"error": "No solution or solver failed", "status": self.solver.StatusName(status)}
