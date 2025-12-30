# app/services/leave_service.py
from sqlmodel import Session
from datetime import datetime
from app.db.models import LeaveRequest, Staff
from app.schemas import LeaveCreate, LeaveStatus, LeaveType
from app.utils.leave_code import generate_unique_leave_code
from app.services.scheduler_service import SchedulerService

AUTO_RESCHEDULE_ENABLED = True  # can be moved to settings/env

class LeaveService:

    @staticmethod
    def create(session: Session, payload: LeaveCreate, submitter_emp: str, org_id: int):
        staff = session.get(Staff, submitter_emp)
        if not staff:
            raise ValueError("Staff not found")

        code = generate_unique_leave_code(session)
        lr = LeaveRequest(
            leave_code=code,
            employee_id=submitter_emp,
            start_date=payload.start_date,
            end_date=payload.end_date,
            leave_type=payload.leave_type,
            reason=payload.reason,
            status=LeaveStatus.PENDING,
            created_at=datetime.utcnow()
        )

        if payload.leave_type in (LeaveType.SICK, LeaveType.URGENT, LeaveType.EMERGENCY):
            lr.status = LeaveStatus.APPROVED
            lr.approved_by = "system_auto"
            lr.approved_at = datetime.utcnow()

        session.add(lr)
        session.commit()
        session.refresh(lr)

        # If auto-approved -> run auto reschedule in the affected window
        reschedule_result = None
        if lr.status == LeaveStatus.APPROVED and AUTO_RESCHEDULE_ENABLED:
            # call scheduler for small window: start..end
            reschedule_result = SchedulerService.run_schedule(session, org_id, lr.start_date, lr.end_date, use_cpsat=False)

        return lr, reschedule_result

    @staticmethod
    def get_by_code(session: Session, code: str):
        from sqlmodel import select
        return session.exec(select(LeaveRequest).where(LeaveRequest.leave_code == code)).first()

    @staticmethod
    def list_by_org(session: Session, org_id: int, skip: int = 0, limit: int = 50):
        from sqlmodel import select
        from app.db.models import Staff
        stmt = select(LeaveRequest).join(Staff).where(Staff.org_id == org_id).offset(skip).limit(limit)
        return session.exec(stmt).all()

    @staticmethod
    def list_by_status(session: Session, org_id: int, status):
        from sqlmodel import select
        from app.db.models import Staff
        return session.exec(select(LeaveRequest).join(Staff).where(Staff.org_id == org_id).where(LeaveRequest.status == status)).all()

    @staticmethod
    def update_status(session: Session, leave_id, status, approver=None):
        lr = session.get(LeaveRequest, leave_id)
        if not lr:
            return None
        lr.status = status
        if status == LeaveStatus.APPROVED:
            lr.approved_by = approver
            lr.approved_at = datetime.utcnow()
        session.add(lr)
        session.commit()
        session.refresh(lr)
        return lr
