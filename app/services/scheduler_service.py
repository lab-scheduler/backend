# app/services/scheduler_service.py
from datetime import date, timedelta
from sqlmodel import Session
from app.scheduler_engine.services.orchestrator import SchedulerOrchestrator

class SchedulerService:
    @staticmethod
    def run_schedule(session: Session, org_id: int, start: date, end: date, use_cpsat: bool = False, cpsat_time: int = 30):
        orchestrator = SchedulerOrchestrator(session, org_id)
        return orchestrator.run(start, end, use_cpsat=use_cpsat, cpsat_time=cpsat_time)

    @staticmethod
    def run_weekly(session: Session, org_id: int, use_cpsat: bool = False):
        start = date.today()
        end = start + timedelta(days=6)
        return SchedulerService.run_schedule(session, org_id, start, end, use_cpsat)

    @staticmethod
    def run_monthly(session: Session, org_id: int, use_cpsat: bool = False):
        start = date.today()
        end = start + timedelta(days=29)
        return SchedulerService.run_schedule(session, org_id, start, end, use_cpsat)
