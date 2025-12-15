# app/services/skill_service.py
from sqlmodel import Session, select
from app.db.models import Skill, Department
from app.schemas import SkillCreate


class SkillService:

    @staticmethod
    def create(session: Session, data: SkillCreate):
        skill = Skill(**data.dict())
        session.add(skill)
        session.commit()
        session.refresh(skill)
        return skill

    @staticmethod
    def list_by_org(session: Session, org_id: int):
        # join department → only skills from this org
        return session.exec(
            select(Skill).join(Department).where(Department.org_id == org_id)
        ).all()

    @staticmethod
    def list_all(session: Session):
        return session.exec(select(Skill)).all()

    @staticmethod
    def get(session: Session, skill_id: str):
        return session.get(Skill, skill_id)

    @staticmethod
    def update(session: Session, skill_id: str, data: SkillCreate):
        skill = session.get(Skill, skill_id)
        if not skill:
            return None

        skill.skill_name = data.skill_name
        skill.required_certification = data.required_certification
        skill.department_id = data.department_id

        session.add(skill)
        session.commit()
        session.refresh(skill)
        return skill

    @staticmethod
    def delete(session: Session, skill_id: str):
        skill = session.get(Skill, skill_id)
        if not skill:
            return False

        session.delete(skill)
        session.commit()
        return True
