# schemas.py (FINAL VERSION)
from sqlmodel import SQLModel
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from enum import Enum
from pydantic import EmailStr


# ============================================================
# ENUMS (same as models.py)
# ============================================================

class RoleType(str, Enum):
    STAFF = "STAFF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class ShiftType(str, Enum):
    DAY = "DAY"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    ON_CALL = "ON_CALL"


class LeaveType(str, Enum):
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    PLANNED = "PLANNED"


class LeaveStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SkillLevel(str, Enum):
    BASIC = "BASIC"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"

# --- Auth / Token schemas ---

class LoginRequest(SQLModel):
    identifier: str        # username OR email OR employee_id
    password: str


class AuthRegister(SQLModel):
    employee_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str
    role: RoleType = RoleType.STAFF    # gunakan enum dari schemas utama


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# ============================================================
# ORGANIZATION SCHEMAS
# ============================================================

class OrganizationCreate(SQLModel):
    name: str
    address: Optional[str] = None


class OrganizationRead(SQLModel):
    id: int
    name: str
    slug: str
    address: Optional[str]


# ============================================================
# DEPARTMENT SCHEMAS
# ============================================================

class DepartmentCreate(SQLModel):
    name: str


class DepartmentRead(SQLModel):
    id: int
    org_id: int
    name: str
    


# ============================================================
# SKILL SCHEMAS
# ============================================================

class SkillCreate(SQLModel):
    department_id: int
    skill_name: str
    required_certification: Optional[str] = None


class SkillRead(SQLModel):
    id: int
    department_id: int
    skill_name: str
    required_certification: Optional[str]


# ============================================================
# STAFF SCHEMAS
# ============================================================

class StaffCreate(SQLModel):
    employee_id: str
    org_id: int
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: RoleType = RoleType.STAFF
    max_hours_per_week: int = 40
    is_supervisor: bool = False


class StaffUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[RoleType] = None
    max_hours_per_week: Optional[int] = None
    is_supervisor: Optional[bool] = None


class StaffRead(SQLModel):
    employee_id: str
    org_id: int
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    role: RoleType
    max_hours_per_week: int
    is_supervisor: bool
    created_at: datetime


# ============================================================
# STAFF SKILLS
# ============================================================

class StaffSkillCreate(SQLModel):
    employee_id: str
    skill_id: int
    proficiency_level: SkillLevel


class StaffSkillRead(SQLModel):
    id: int
    employee_id: str
    skill_id: int
    proficiency_level: SkillLevel


# ============================================================
# SHIFT SCHEMAS
# ============================================================

class ShiftCreate(SQLModel):
    org_id: int
    shift_date: date
    shift_type: ShiftType
    department_id: int
    min_staff: int
    max_staff: int
    priority: int = 1
    requires_supervisor: bool = False
    hours: Optional[int] = 8
    required_skill_ids: Optional[List[int]] = None


class ShiftRequiredSkillRead(SQLModel):
    skill_id: int
    skill_name: str
    required_certification: Optional[str]
    

class ShiftRead(SQLModel):
    id: int
    shift_date: date
    shift_type: str
    department_id: int
    min_staff: int
    max_staff: int
    priority: int
    requires_supervisor: bool
    hours: int

    required_skills: List[ShiftRequiredSkillRead] = []


# ============================================================
# SHIFT ASSIGNMENT SCHEMAS
# ============================================================

class ShiftAssignmentCreate(SQLModel):
    shift_id: int
    employee_id: str


class ShiftAssignmentRead(SQLModel):
    id: UUID
    shift_id: int
    employee_id: str
    assigned_hours: int
    assigned_at: datetime


# ============================================================
# LEAVE REQUEST SCHEMAS
# ============================================================

class LeaveCreate(SQLModel):
    employee_id: str
    start_date: date
    end_date: date
    leave_type: LeaveType
    reason: Optional[str] = None


class LeaveUpdate(SQLModel):
    status: Optional[LeaveStatus] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class LeaveRead(SQLModel):
    id: UUID
    leave_code: str
    employee_id: str
    start_date: date
    end_date: date
    leave_type: LeaveType
    status: LeaveStatus
    reason: Optional[str]
    submitted_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]



