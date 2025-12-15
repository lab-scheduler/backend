# app/scheduler_engine/adapters/model_mapper.py
from dataclasses import dataclass
from datetime import date
from typing import List, Dict

# Engine dataclasses used by core engines

@dataclass
class EngineStaff:
    employee_id: str
    name: str
    org_id: int
    max_hours_per_week: float
    is_supervisor: bool
    preferred_shifts: List[str]
    skills: Dict[int, int]  # skill_id -> level
    role: str  # Staff role (STAFF, MANAGER, ADMIN)

    def can_work_in_department(self, dept_id: int) -> bool:
        # assume staff has allowed_depts attr if needed; fallback True
        return True

    def has_skill(self, skill_id: int) -> bool:
        return skill_id in self.skills

    def is_available_on(self, check_date: date) -> bool:
        # for CPSAT we rely on engine.leaves to check availability
        return True

    def estimate_weekly_utilization(self) -> float:
        # simple placeholder; real one comes from engine.staff_hours mapping
        return 0.0


@dataclass
class EngineShift:
    id: int
    shift_date: date
    shift_type: str
    department_id: int
    required_skill_ids: List[int]
    min_staff: int
    max_staff: int
    priority: int
    requires_supervisor: bool
    hours: int = 8
    assigned_staff_ids: List[str] = None

    def __post_init__(self):
        if self.assigned_staff_ids is None:
            self.assigned_staff_ids = []

@dataclass
class EngineLeave:
    id: int
    employee_id: str
    start_date: date
    end_date: date
    status: str
    leave_type: str

    def is_urgent(self):
        return self.leave_type in ("URGENT", "EMERGENCY", "SICK")
