from sqlmodel import SQLModel, Field, Column, Relationship, JSON
from sqlalchemy import ForeignKey
from typing import Optional, List
from uuid import uuid4, UUID
from datetime import datetime, date
from enum import Enum
import os

# Helper to handle schema for different databases
def get_table_args(schema_name: str = "scheduler_dev"):
    """Return table args with schema only for non-SQLite databases"""
    db_url = os.getenv("DB_ENGINE", "")
    if "sqlite" in db_url.lower() or not db_url:
        return {}
    return {"schema": schema_name}


# ====================================================
# ENUMS
# ====================================================
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


# MODELS

class AuthUser(SQLModel, table=True):
    __tablename__ = "auth_users"
    __table_args__ = get_table_args()

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    employee_id: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)

    password_hash: str

    role: str = Field(default="STAFF")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    name: str
    address: Optional[str] = None
    slug: str = Field(index=True, unique=True)

    departments: List["Department"] = Relationship(back_populates="organization")
    staff: List["Staff"] = Relationship(back_populates="organization")
    shifts: List["Shift"] = Relationship(back_populates="organization")

class Department(SQLModel, table=True):
    __tablename__ = "departments"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    org_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.organizations.id")))
    name: str

    organization: Organization = Relationship(back_populates="departments")
    skills: List["Skill"] = Relationship(back_populates="department")

class Skill(SQLModel, table=True):
    __tablename__ = "skills"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    department_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.departments.id")))
    skill_name: str
    required_certification: Optional[str] = None

    department: Department = Relationship(back_populates="skills")
    staff_links: List["StaffSkill"] = Relationship(back_populates="skill")
    shift_requirements: List["ShiftRequiredSkill"] = Relationship(back_populates="skill")


class Staff(SQLModel, table=True):
    __tablename__ = "staff"
    __table_args__ = get_table_args()

    employee_id: str = Field(primary_key=True)
    org_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.organizations.id")))
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: RoleType
    max_hours_per_week: int = 40
    is_supervisor: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    organization: Organization = Relationship(back_populates="staff")
    skills: List["StaffSkill"] = Relationship(back_populates="staff")
    assignments: List["ShiftAssignment"] = Relationship(back_populates="staff")
    leaves: List["LeaveRequest"] = Relationship(back_populates="staff")

class StaffSkill(SQLModel, table=True):
    __tablename__ = "staff_skills"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    employee_id: str = Field(sa_column=Column(ForeignKey("scheduler_dev.staff.employee_id")))
    skill_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.skills.id")))
    proficiency_level: SkillLevel

    staff: Staff = Relationship(back_populates="skills")
    skill: Skill = Relationship(back_populates="staff_links")

class Shift(SQLModel, table=True):
    __tablename__ = "shifts"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    org_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.organizations.id")))
    shift_date: date
    shift_type: ShiftType
    department_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.departments.id")))
    min_staff: int
    max_staff: int
    priority: int = 1
    hours: int = 8
    requires_supervisor: bool = False

    organization: Organization = Relationship(back_populates="shifts")
    department: Department = Relationship()
    assignments: List["ShiftAssignment"] = Relationship(back_populates="shift")
    required_skills: List["ShiftRequiredSkill"] = Relationship(back_populates="shift")

    
    
class ShiftRequiredSkill(SQLModel, table=True):
    __tablename__ = "shift_required_skills"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    shift_id: int = Field(
        sa_column=Column(ForeignKey("scheduler_dev.shifts.id", ondelete="CASCADE"))
    )
    skill_id: int = Field(
        sa_column=Column(ForeignKey("scheduler_dev.skills.id", ondelete="CASCADE"))
    )

    # Relationships
    shift: "Shift" = Relationship(back_populates="required_skills")
    skill: "Skill" = Relationship(back_populates="shift_requirements")


class ShiftAssignment(SQLModel, table=True):
    __tablename__ = "shift_assignments"
    __table_args__ = get_table_args()

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    shift_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.shifts.id")))
    employee_id: str = Field(sa_column=Column(ForeignKey("scheduler_dev.staff.employee_id")))
    assigned_hours: int = 8
    assigned_at: datetime = Field(default_factory=datetime.utcnow)

    shift: Shift = Relationship(back_populates="assignments")
    staff: Staff = Relationship(back_populates="assignments")

class LeaveRequest(SQLModel, table=True):
    __tablename__ = "leave_requests"
    __table_args__ = get_table_args()

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    leave_code: str
    employee_id: str = Field(sa_column=Column(ForeignKey("scheduler_dev.staff.employee_id")))
    start_date: date
    end_date: date
    leave_type: LeaveType
    status: LeaveStatus = LeaveStatus.PENDING
    reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    staff: Staff = Relationship(back_populates="leaves")
    

class WorkPipeline(SQLModel, table=True):
    __tablename__ = "work_pipelines"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    org_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.organizations.id")))
    name: str
    department_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.departments.id")))
    start_date: date
    end_date: date
    estimated_staff_hours: int = Field(default=8)
    is_recurring: bool = Field(default=True)
    recurrence_days: List[int] = Field(sa_column=Column(JSON))  # 0=Monday ... 6=Sunday
    priority: int = Field(default=3)

    required_skills: List["PipelineRequiredSkill"] = Relationship(back_populates="pipeline")


class PipelineRequiredSkill(SQLModel, table=True):
    __tablename__ = "pipeline_required_skills"
    __table_args__ = get_table_args()

    id: int = Field(primary_key=True)
    pipeline_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.work_pipelines.id")))
    skill_id: int = Field(sa_column=Column(ForeignKey("scheduler_dev.skills.id")))

    pipeline: "WorkPipeline" = Relationship(back_populates="required_skills")
    skill: "Skill" = Relationship()

