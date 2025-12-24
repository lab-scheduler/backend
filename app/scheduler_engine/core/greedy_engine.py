from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from app.scheduler_engine.adapters.model_mapper import EngineShift, EngineStaff, EngineLeave
from app.scheduler_engine.core.scoring_engine import ScoringEngine


class SchedulingConflict:
    def __init__(self, severity: str, message: str, shift_id: Optional[int] = None):
        self.severity = severity
        self.message = message
        self.shift_id = shift_id

    def to_dict(self):
        return {"severity": self.severity, "message": self.message, "shift_id": self.shift_id}


class GreedyEngine:
    """
    Implements:
      - assign_staff_to_shift
      - auto_schedule_shift
      - schedule_date_range
    """
    def __init__(self):
        self.staff: List[EngineStaff] = []
        self.shifts: List[EngineShift] = []
        self.leaves: List[EngineLeave] = []
        # track hours per staff per date
        self.staff_hours = defaultdict(lambda: defaultdict(float))
        self.scorer = ScoringEngine()

    # ---------- loaders (populated by adapter) ----------
    def add_staff(self, s: EngineStaff):
        self.staff.append(s)

    def add_shift(self, sh: EngineShift):
        self.shifts.append(sh)

    def add_leave(self, lv: EngineLeave):
        self.leaves.append(lv)

    # ---------- availability ----------
    def is_staff_available(self, staff: EngineStaff, check_date: date) -> bool:
        # approved leaves block availability
        for lv in self.leaves:
            if lv.employee_id == staff.employee_id and lv.status == "APPROVED":
                if lv.start_date <= check_date <= lv.end_date:
                    return False
        return True

    # ---------- hours ----------
    def _record_hours(self, employee_id: str, work_date: date, hours: float):
        self.staff_hours[employee_id][work_date] += hours

    def _get_weekly_hours(self, employee_id: str, week_start: date) -> float:
        total = 0.0
        for i in range(7):
            d = week_start + timedelta(days=i)
            total += self.staff_hours[employee_id].get(d, 0.0)
        return total

    # ---------- assignment ----------
    def can_assign(self, staff: EngineStaff, shift: EngineShift) -> Tuple[bool, str]:
        # check capability: department, skills
        if not staff.can_work_in_department(shift.department_id):
            return False, "Cannot work in department"
        for req in shift.required_skill_ids:
            if not staff.has_skill(req):
                return False, "Missing required skill"
        return True, "ok"

    def assign_staff_to_shift(self, staff: EngineStaff, shift: EngineShift) -> Tuple[bool, str]:
        # availability
        if not self.is_staff_available(staff, shift.shift_date):
            return False, "On leave"

        # Check if already assigned to another shift on the same day
        if staff.employee_id in self.staff_hours and shift.shift_date in self.staff_hours[staff.employee_id]:
            if self.staff_hours[staff.employee_id][shift.shift_date] >= 8:  # Assuming 8 hours per shift
                return False, "Already assigned to another shift today"

        # weekly hours
        week_start = shift.shift_date - timedelta(days=shift.shift_date.weekday())
        weekly_hours = self._get_weekly_hours(staff.employee_id, week_start)
        if weekly_hours + shift.hours > staff.max_hours_per_week:
            return False, "Would exceed weekly hours"

        # shift-specific checks
        can_assign, reason = self.can_assign(staff, shift)
        if not can_assign:
            return False, reason

        # perform assignment
        shift.assigned_staff_ids.append(staff.employee_id)
        self._record_hours(staff.employee_id, shift.shift_date, shift.hours)
        return True, "Assigned"

    # ---------- replacement finder ----------
    def find_replacement(self, shift: EngineShift, unavailable_employee_id: str) -> Optional[EngineStaff]:
        for s in self.staff:
            if s.employee_id == unavailable_employee_id:
                continue
            if not self.is_staff_available(s, shift.shift_date):
                continue
            can_assign, _ = self.can_assign(s, shift)
            if not can_assign:
                continue
            week_start = shift.shift_date - timedelta(days=shift.shift_date.weekday())
            if self._get_weekly_hours(s.employee_id, week_start) + shift.hours <= s.max_hours_per_week:
                return s
        return None

    # ---------- auto_schedule_shift (score + greedy assign) ----------
    def auto_schedule_shift(self, shift: EngineShift) -> List[SchedulingConflict]:
        conflicts = []
        # get available staff for department
        available = [s for s in self.staff if s.can_work_in_department(shift.department_id) and self.is_staff_available(s, shift.shift_date)]
        if not available:
            conflicts.append(SchedulingConflict("critical", f"No available staff for dept {shift.department_id} on {shift.shift_date}", shift.id))
            return conflicts
        # score staff
        scored = []
        for s in available:
            score = self.scorer.score_staff_for_shift(s, shift)  # uses scoring_engine
            if score > 0:
                scored.append((s, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        assigned = 0
        supervisor_assigned = False
        for s, _ in scored:
            if assigned >= shift.max_staff:
                break
            ok, reason = self.assign_staff_to_shift(s, shift)
            if ok:
                assigned += 1
                if s.is_supervisor:
                    supervisor_assigned = True
        if assigned < shift.min_staff:
            conflicts.append(SchedulingConflict("critical", f"Understaffed {assigned}/{shift.min_staff}", shift.id))
        if shift.requires_supervisor and not supervisor_assigned:
            conflicts.append(SchedulingConflict("warning", "No supervisor assigned", shift.id))
        return conflicts

    # ---------- schedule range ----------
    def schedule_date_range(self, start_date: date, end_date: date) -> Dict[str, List[Dict]]:
        # operate on copy of shifts sorted by priority & date
        shifts = [s for s in self.shifts if start_date <= s.shift_date <= end_date]
        shifts.sort(key=lambda s: (s.shift_date, -s.priority))
        conflicts_by_date = defaultdict(list)

        # First pass: Remove any staff on leave from their assigned shifts
        for sh in shifts:
            # Check each assigned staff member
            staff_to_remove = []
            for staff_id in sh.assigned_staff_ids:
                # Find the staff object
                staff = next((s for s in self.staff if s.employee_id == staff_id), None)
                if staff and not self.is_staff_available(staff, sh.shift_date):
                    staff_to_remove.append(staff_id)
                    # Record that we removed someone due to leave
                    conflicts_by_date[str(sh.shift_date)].append({
                        "severity": "info",
                        "message": f"Removed {staff_id} from shift due to approved leave",
                        "shift_id": sh.id
                    })

            # Remove staff on leave from the shift
            for staff_id in staff_to_remove:
                sh.assigned_staff_ids.remove(staff_id)
                # Subtract hours from tracking
                self.staff_hours[staff_id][sh.shift_date] = max(0, self.staff_hours[staff_id][sh.shift_date] - sh.hours)

        # Second pass: Schedule shifts that need more staff
        for sh in shifts:
            if len(sh.assigned_staff_ids) < sh.min_staff:
                confs = self.auto_schedule_shift(sh)
                for c in confs:
                    conflicts_by_date[str(sh.shift_date)].append(c.to_dict())

        return conflicts_by_date
