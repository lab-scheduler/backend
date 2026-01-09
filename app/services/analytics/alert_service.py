# app/services/analytics/alert_service.py
"""
Alert System Service - Answers: "What are the critical issues I need to address?"

Aggregates all critical issues into actionable alerts with severity classification.
"""
from datetime import date, datetime, timedelta
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session
import uuid

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    AlertSystem,
    Alert,
    AlertSummary
)
from app.db.models import Department


class AlertService:
    """Alert aggregation and classification service"""
    
    @staticmethod
    def get_alerts(session: Session, org_id: int, severity_filter: str = None, 
                   category_filter: str = None) -> AlertSystem:
        """
        Get all current alerts for the organization.
        
        Answers: "What are the critical issues I need to address?"
        """
        # Analyze next 7 days by default
        start_date = date.today()
        end_date = start_date + timedelta(days=7)
        
        # Load data
        adapter = DBAdapter(session, org_id)
        shifts = adapter.load_shifts(start_date, end_date)
        staff_list = adapter.load_staff()
        departments = AlertService._load_departments(session, org_id)
        
        # Build lookups
        dept_map = {d.id: d for d in departments}
        staff_map = {s.employee_id: s for s in staff_list}
        
        # Group assignments
        assignments_by_shift = defaultdict(list)
        all_assignments = adapter.load_assignments_bulk(start_date, end_date)
        for assignment in all_assignments:
            assignments_by_shift[assignment.shift_id].append(assignment)
        
        # Collect all alerts
        alerts = []
        
        # 1. Staffing alerts
        alerts.extend(AlertService._generate_staffing_alerts(
            shifts, assignments_by_shift, dept_map
        ))
        
        # 2. Supervisor alerts
        alerts.extend(AlertService._generate_supervisor_alerts(
            shifts, assignments_by_shift, staff_map, dept_map
        ))
        
        # 3. Skill coverage alerts
        alerts.extend(AlertService._generate_skill_alerts(
            shifts, assignments_by_shift, staff_map, dept_map
        ))
        
        # 4. Workload alerts (overtime, burnout risk)
        alerts.extend(AlertService._generate_workload_alerts(
            staff_list, all_assignments, shifts
        ))
        
        # Apply filters
        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter.upper()]
        if category_filter:
            alerts = [a for a in alerts if a.category == category_filter.upper()]
        
        # Sort by severity (CRITICAL first)
        severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        alerts.sort(key=lambda a: (severity_order[a.severity], a.created_at))
        
        # Calculate summary
        summary = AlertService._calculate_summary(alerts)
        
        return AlertSystem(
            alerts=alerts,
            summary=summary
        )
    
    @staticmethod
    def _generate_staffing_alerts(shifts: List, assignments_by_shift: Dict, dept_map: Dict) -> List[Alert]:
        """Generate alerts for understaffed shifts"""
        alerts = []
        
        understaffed_by_dept = defaultdict(list)
        
        for shift in shifts:
            assigned = assignments_by_shift.get(shift.id, [])
            if len(assigned) < shift.min_staff:
                understaffed_by_dept[shift.department_id].append(shift)
        
        for dept_id, dept_shifts in understaffed_by_dept.items():
            dept = dept_map.get(dept_id)
            dept_name = dept.name if dept else f"Department {dept_id}"
            
            gap_total = sum(s.min_staff - len(assignments_by_shift.get(s.id, [])) for s in dept_shifts)
            
            severity = "CRITICAL" if len(dept_shifts) > 5 or gap_total > 10 else "WARNING"
            
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                severity=severity,
                category="STAFFING",
                title=f"{dept_name}: {len(dept_shifts)} understaffed shifts",
                description=f"{dept_name} has {len(dept_shifts)} shifts below minimum staffing requirements (total gap: {gap_total} staff)",
                affected_entities=[str(s.id) for s in dept_shifts],
                created_at=datetime.utcnow(),
                actionable=True,
                recommended_action=f"Assign {gap_total} additional staff to {dept_name} or adjust shift requirements"
            ))
        
        return alerts
    
    @staticmethod
    def _generate_supervisor_alerts(shifts: List, assignments_by_shift: Dict, 
                                    staff_map: Dict, dept_map: Dict) -> List[Alert]:
        """Generate alerts for missing supervisors"""
        alerts = []
        
        missing_supervisor_shifts = []
        
        for shift in shifts:
            if not shift.requires_supervisor:
                continue
            
            assigned = assignments_by_shift.get(shift.id, [])
            has_supervisor = any(
                staff_map.get(a.employee_id, {}).is_supervisor
                for a in assigned
                if a.employee_id in staff_map
            )
            
            if not has_supervisor:
                missing_supervisor_shifts.append(shift)
        
        if missing_supervisor_shifts:
            # Group by department
            by_dept = defaultdict(list)
            for shift in missing_supervisor_shifts:
                by_dept[shift.department_id].append(shift)
            
            for dept_id, dept_shifts in by_dept.items():
                dept = dept_map.get(dept_id)
                dept_name = dept.name if dept else f"Department {dept_id}"
                
                alerts.append(Alert(
                    id=str(uuid.uuid4()),
                    severity="CRITICAL",
                    category="SUPERVISOR",
                    title=f"{dept_name}: {len(dept_shifts)} shifts missing supervisor",
                    description=f"{len(dept_shifts)} shifts require supervisor coverage but none is assigned",
                    affected_entities=[str(s.id) for s in dept_shifts],
                    created_at=datetime.utcnow(),
                    actionable=True,
                    recommended_action=f"Assign supervisors to {len(dept_shifts)} shifts in {dept_name}"
                ))
        
        return alerts
    
    @staticmethod
    def _generate_skill_alerts(shifts: List, assignments_by_shift: Dict, 
                               staff_map: Dict, dept_map: Dict) -> List[Alert]:
        """Generate alerts for skill coverage gaps"""
        alerts = []
        
        skill_gaps_by_dept = defaultdict(list)
        
        for shift in shifts:
            if not hasattr(shift, 'required_skill_ids') or not shift.required_skill_ids:
                continue
            
            assigned = assignments_by_shift.get(shift.id, [])
            
            # Get assigned skills
            assigned_skills = set()
            for assignment in assigned:
                staff = staff_map.get(assignment.employee_id)
                if staff and hasattr(staff, 'skills'):
                    assigned_skills.update(staff.skills.keys())
            
            # Check for missing skills
            required_skills = set(shift.required_skill_ids)
            missing_skills = required_skills - assigned_skills
            
            if missing_skills:
                skill_gaps_by_dept[shift.department_id].append((shift, missing_skills))
        
        for dept_id, gaps in skill_gaps_by_dept.items():
            dept = dept_map.get(dept_id)
            dept_name = dept.name if dept else f"Department {dept_id}"
            
            total_gaps = sum(len(missing) for _, missing in gaps)
            
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                severity="WARNING",
                category="SKILLS",
                title=f"{dept_name}: {len(gaps)} shifts with skill gaps",
                description=f"{len(gaps)} shifts are missing required skills (total {total_gaps} skill gaps)",
                affected_entities=[str(s.id) for s, _ in gaps],
                created_at=datetime.utcnow(),
                actionable=True,
                recommended_action=f"Assign staff with required skills or provide training"
            ))
        
        return alerts
    
    @staticmethod
    def _generate_workload_alerts(staff_list: List, assignments: List, shifts: List) -> List[Alert]:
        """Generate alerts for workload issues"""
        alerts = []
        
        # Build shift map
        shift_map = {s.id: s for s in shifts}
        
        # Group by staff
        by_staff = defaultdict(list)
        for assignment in assignments:
            by_staff[assignment.employee_id].append(assignment)
        
        high_workload_staff = []
        
        for staff in staff_list:
            staff_assignments = by_staff.get(staff.employee_id, [])
            if not staff_assignments:
                continue
            
            total_hours = len(staff_assignments) * 8
            
            # Check for overtime (assuming 40 hours per week, 7 day period)
            if total_hours > 56:  # More than 56 hours in 7 days
                high_workload_staff.append((staff, total_hours))
        
        if high_workload_staff:
            severity = "CRITICAL" if len(high_workload_staff) > 5 else "WARNING"
            
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                severity=severity,
                category="WORKLOAD",
                title=f"{len(high_workload_staff)} staff members with excessive workload",
                description=f"{len(high_workload_staff)} staff members are scheduled for more than 56 hours in the next 7 days",
                affected_entities=[s.employee_id for s, _ in high_workload_staff],
                created_at=datetime.utcnow(),
                actionable=True,
                recommended_action="Redistribute workload to prevent burnout"
            ))
        
        return alerts
    
    @staticmethod
    def _calculate_summary(alerts: List[Alert]) -> AlertSummary:
        """Calculate alert summary statistics"""
        critical = sum(1 for a in alerts if a.severity == "CRITICAL")
        warning = sum(1 for a in alerts if a.severity == "WARNING")
        info = sum(1 for a in alerts if a.severity == "INFO")
        
        return AlertSummary(
            critical=critical,
            warning=warning,
            info=info,
            total=len(alerts)
        )
    
    @staticmethod
    def _load_departments(session: Session, org_id: int) -> List[Department]:
        """Load departments for organization"""
        from sqlmodel import select
        return session.exec(select(Department).where(Department.org_id == org_id)).all()
