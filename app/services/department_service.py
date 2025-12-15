# app/services/department_service.py
from sqlmodel import Session, select
from app.db.models import Department
from app.schemas import DepartmentCreate


class DepartmentService:

    @staticmethod
    def create(session: Session, data: DepartmentCreate):
        dept = Department(**data.dict())
        session.add(dept)
        session.commit()
        session.refresh(dept)
        return dept

    @staticmethod
    def list(session: Session, org_id: int):
        return session.exec(
            select(Department).where(Department.org_id == org_id)
        ).all()

    @staticmethod
    def get(session: Session, dept_id: int):
        return session.get(Department, dept_id)

    @staticmethod
    def update(session: Session, dept_id: int, data: DepartmentCreate):
        dept = session.get(Department, dept_id)
        if not dept:
            return None

        dept.name = data.name
        dept.org_id = data.org_id

        session.add(dept)
        session.commit()
        session.refresh(dept)
        return dept

    @staticmethod
    def delete(session: Session, dept_id: int):
        dept = session.get(Department, dept_id)
        if not dept:
            return False

        session.delete(dept)
        session.commit()
        return True
