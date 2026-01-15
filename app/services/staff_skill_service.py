# app/services/staff_skill_service.py

from sqlmodel import Session, select
from app.db.models import StaffSkill, Skill, Department, Staff
from app.schemas import StaffSkillCreate
from uuid import UUID


class StaffSkillService:

    @staticmethod
    def create(session: Session, data: StaffSkillCreate):
        record = StaffSkill(**data.dict())
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def list_by_staff(session: Session, staff_id: str):
        return session.exec(
            select(StaffSkill).where(StaffSkill.employee_id == staff_id)
        ).all()

    @staticmethod
    def list_by_org(session: Session, org_id: int):
        """
        Returns all staff skills for all staff within an organization.
        Useful for analytics (skill gaps, training needs, etc).
        """

        return session.exec(
            select(StaffSkill)
            .join(Staff, StaffSkill.employee_id == Staff.employee_id)
            .where(Staff.org_id == org_id)
        ).all()

    @staticmethod
    def get(session: Session, staff_skill_id: UUID):
        return session.get(StaffSkill, staff_skill_id)

    @staticmethod
    def update(session: Session, staff_skill_id: UUID, data: StaffSkillCreate):
        record = session.get(StaffSkill, staff_skill_id)
        if not record:
            return None

        # Fields allowed to update:
        record.skill_id = data.skill_id
        record.proficiency_level = data.proficiency_level
        record.employee_id = data.employee_id  # ensure consistency

        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def delete(session: Session, staff_skill_id: UUID):
        record = session.get(StaffSkill, staff_skill_id)
        if not record:
            return False

        session.delete(record)
        session.commit()
        return True

    @staticmethod
    def get_staff(session: Session, staff_id: str):
        """Get staff member by ID"""
        return session.get(Staff, staff_id)

    @staticmethod
    def get_skill(session: Session, skill_id: int):
        """Get skill by ID"""
        return session.get(Skill, skill_id)

    @staticmethod
    def get_department_by_skill(session: Session, skill_id: int):
        """Get department associated with a skill"""
        skill = session.get(Skill, skill_id)
        return session.get(Department, skill.department_id) if skill else None
