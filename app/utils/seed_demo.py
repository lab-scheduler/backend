# app/utils/seed_demo.py
from datetime import date, timedelta
from sqlmodel import select
from app.db.session import engine
from app.db.models import Staff, Skill, StaffSkill, Shift, ShiftAssignment, LeaveRequest
from app.services.scheduler_service import SchedulerService
from app.services.optimization_service import OptimizationService
from sqlmodel import Session

def _clear_demo(session: Session):
    # careful: only used for demo. Delete all demo-related rows.
    for row in session.exec(select(ShiftAssignment)).all():
        session.delete(row)
    for row in session.exec(select(Shift)).all():
        session.delete(row)
    for row in session.exec(select(StaffSkill)).all():
        session.delete(row)
    for row in session.exec(select(Skill)).all():
        session.delete(row)
    for row in session.exec(select(LeaveRequest)).all():
        session.delete(row)
    for row in session.exec(select(Staff)).all():
        session.delete(row)
    session.commit()

def _create_basic_set(session: Session, days: int):
    # sample staff
    sample_staff = [
        ("E001","Dr. Sarah Chen", True),
        ("E002","Marcus Tan", False),
        ("E003","Lisa Wong", False),
        ("E004","David Ng", False),
        ("E005","Emily Lim", False),
        ("E006","Rajesh Kumar", False),
        ("E007","Priya Sharma", False),
        ("E008","Kevin Tan", False),
    ]
    staff_objs = []
    for emp, name, sup in sample_staff:
        s = Staff(employee_id=emp, name=name, is_supervisor=sup, max_hours_per_week=40, is_active=True)
        session.add(s); staff_objs.append(s)
    session.commit()
    for s in staff_objs: session.refresh(s)

    # skills
    skills = [("Hematology","HEMATOLOGY"),("Microbiology","MICROBIO"),("Chemistry","CHEMISTRY")]
    skill_objs = []
    for n, d in skills:
        sk = Skill(name=n, department=d)
        session.add(sk); skill_objs.append(sk)
    session.commit()
    for sk in skill_objs: session.refresh(sk)

    # map staff skills
    mapping = [(0,0),(1,0),(2,1),(3,2),(4,2),(5,0),(6,1),(7,2)]
    for sidx, skidx in mapping:
        ss = StaffSkill(employee_id=staff_objs[sidx].employee_id, skill_id=skill_objs[skidx].id, level="INTERMEDIATE")
        session.add(ss)
    session.commit()

    # create shifts
    start = date.today()
    departments = ["HEMATOLOGY","MICROBIO","CHEMISTRY"]
    shifts = []
    for i in range(days):
        d = start + timedelta(days=i)
        for dept in departments:
            sh = Shift(date=d, shift_type="DAY", department=dept, min_staff=1, max_staff=2, requires_supervisor=False)
            session.add(sh); shifts.append(sh)
    session.commit()
    for sh in shifts: session.refresh(sh)

    return {"staff": staff_objs, "skills": skill_objs, "shifts": shifts}

def _create_heavy_conflict(session: Session, days: int):
    # create fewer staff and many shifts → cause conflicts
    sample_staff = [
        ("E100","On-call A", False),
        ("E101","On-call B", False),
        ("E102","Supervisor A", True)
    ]
    staff_objs = []
    for emp, name, sup in sample_staff:
        s = Staff(employee_id=emp, name=name, is_supervisor=sup, max_hours_per_week=40, is_active=True)
        session.add(s); staff_objs.append(s)
    session.commit()
    for s in staff_objs: session.refresh(s)

    # many shifts per day
    start = date.today()
    shifts = []
    departments = ["HEMATOLOGY","MICROBIO","CHEMISTRY","BLOODBANK"]
    for i in range(days):
        d = start + timedelta(days=i)
        for dept in departments:
            # make many shifts with high min_staff to create understaffed scenario
            sh = Shift(date=d, shift_type="DAY", department=dept, min_staff=2, max_staff=3, requires_supervisor=False)
            session.add(sh); shifts.append(sh)
    session.commit()
    for sh in shifts: session.refresh(sh)
    return {"staff": staff_objs, "shifts": shifts}

def _create_last_minute_leave(session: Session, days: int):
    payload = _create_basic_set(session, days)
    # approve urgent leave for one staff tomorrow
    staff = session.exec(select(Staff)).first()
    if staff:
        leave = LeaveRequest(employee_id=staff.employee_id, start_date=date.today(), end_date=date.today()+timedelta(days=2), leave_type="URGENT", status="APPROVED")
        session.add(leave); session.commit(); session.refresh(leave)
    return payload

def seed_demo(demo_type: str = "basic", days: int = 7):
    with Session(engine) as session:
        _clear_demo(session)
        if demo_type == "basic":
            _create_basic_set(session, days)
        elif demo_type == "heavy_conflict":
            _create_heavy_conflict(session, days)
        elif demo_type == "last_minute_leave":
            _create_last_minute_leave(session, days)
        else:
            _create_basic_set(session, days)

        # run scheduler & analyzer
        svc = SchedulerService(session)
        start = date.today()
        end = start + timedelta(days=days-1)
        sched_result = svc.run_scheduler(start, end)
        # build state for analysis
        assignments = session.exec(select(ShiftAssignment)).all()
        shifts = session.exec(select(Shift).where(Shift.date >= start, Shift.date <= end)).all()
        state = {
            "assignments": [{"shift_id": a.shift_id, "staff_id": a.staff_id} for a in assignments],
            "shifts": {s.id: {"min_staff": s.min_staff, "requires_supervisor": s.requires_supervisor, "date": s.date, "department": s.department, "hours": getattr(s, "hours", None)} for s in shifts}
        }
        opt = OptimizationService(session, state)
        report = opt.analyze()

        # build payload for frontend
        staff_objs = session.exec(select(Staff)).all()
        payload = {
            "staff": [{"employee_id": s.employee_id, "name": s.name, "is_supervisor": s.is_supervisor} for s in staff_objs],
            "shifts_by_date": {},
            "assignments": [{"shift_id": a.shift_id, "employee_id": a.employee_id} for a in assignments],
            "scheduler_result": sched_result,
            "analysis": report
        }
        for sh in shifts:
            payload["shifts_by_date"].setdefault(str(sh.date), []).append({
                "id": sh.id, "department": sh.department, "shift_type": sh.shift_type, "min_staff": sh.min_staff, "max_staff": sh.max_staff
            })
        return payload
