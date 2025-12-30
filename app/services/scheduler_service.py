# app/services/scheduler_service.py
from datetime import date, timedelta
from sqlmodel import Session
from app.scheduler_engine.services.orchestrator import SchedulerOrchestrator
from app.core.logging import scheduler_logger

class SchedulerService:
    @staticmethod
    def run_schedule(session: Session, org_id: int, start: date, end: date, use_cpsat: bool = False, cpsat_time: int = 30):
        scheduler_logger.log_scheduler_run(
            org_id=org_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            use_cpsat=use_cpsat,
            metadata={"cpsat_time": cpsat_time}
        )
        orchestrator = SchedulerOrchestrator(session, org_id)
        result = orchestrator.run(start, end, use_cpsat=use_cpsat, cpsat_time=cpsat_time)
        
        scheduler_logger.log_scheduler_result(
            org_id=org_id,
            success=result.get("ok", False),
            shifts_count=result.get("meta", {}).get("shifts_loaded", 0),
            staff_count=result.get("meta", {}).get("staff_count", 0)
        )
        return result

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
