# app/services/analytics/shift_risk_service.py
"""
Shift Risk Analytics Service - Answers: "Which shifts or departments are most at risk?"

Provides comprehensive risk assessment for individual shifts and departments.
"""
from datetime import date
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    ShiftRiskAnalysis,
    ShiftRisk,
    DepartmentRisk
)
from app.db.models import Department


class ShiftRiskAnalyticsService:
    """Shift and department risk analysis service"""
    
    @staticmethod
    def analyze_shift_risks(session: Session, org_id: int, start: date, end: date) -> ShiftRiskAnalysis:
        """
        Comprehensive shift and department risk analysis.
        
        Answers: "Which shifts or departments are most at risk?"
        """
        # Load data
        adapter = DBAdapter(session, org_id)
        shifts = adapter.load_shifts(start, end)
        staff_list = adapter.load_staff()
        departments = ShiftRiskAnalyticsService._load_departments(session, org_id)
        
        # Build lookups
        dept_map = {d.id: d for d in departments}
        staff_map = {s.employee_id: s for s in staff_list}
        
        # Group assignments by shift
        assignments_by_shift = defaultdict(list)
        all_assignments = adapter.load_assignments_bulk(start, end)
        for assignment in all_assignments:
            assignments_by_shift[assignment.shift_id].append(assignment)
        
        # Analyze each shift
        shift_risks = []
        shifts_by_dept = defaultdict(list)
        
        for shift in shifts:
            shift_assignments = assignments_by_shift.get(shift.id, [])
            
            # Calculate risk score and factors
            risk_score, risk_factors = ShiftRiskAnalyticsService._calculate_shift_risk(
                shift, shift_assignments, staff_map
            )
            
            # Determine coverage status
            coverage_status = ShiftRiskAnalyticsService._get_coverage_status(
                shift, len(shift_assignments)
            )
            
            # Check supervisor presence
            has_supervisor = any(
                staff_map.get(a.employee_id, {}).is_supervisor
                for a in shift_assignments
                if a.employee_id in staff_map
            )
            
            # Check skill gaps
            skill_gaps = ShiftRiskAnalyticsService._identify_skill_gaps(
                shift, shift_assignments, staff_map
            )
            
            dept = dept_map.get(shift.department_id)
            
            shift_risk = ShiftRisk(
                shift_id=shift.id,
                date=shift.shift_date,
                shift_type=shift.shift_type,
                department_name=dept.name if dept else f"Dept {shift.department_id}",
                department_id=shift.department_id,
                risk_score=risk_score,
                risk_factors=risk_factors,
                coverage_status=coverage_status,
                assigned_count=len(shift_assignments),
                required_count=shift.min_staff,
                has_supervisor=has_supervisor,
                skill_gaps=skill_gaps
            )
            
            shift_risks.append(shift_risk)
            shifts_by_dept[shift.department_id].append(shift_risk)
        
        # Sort by risk score (highest first)
        shift_risks.sort(key=lambda x: x.risk_score, reverse=True)
        
        # Analyze departments
        department_risks = ShiftRiskAnalyticsService._analyze_departments(
            shifts_by_dept, dept_map
        )
        
        return ShiftRiskAnalysis(
            shift_risks=shift_risks,
            department_risks=department_risks,
            period={
                "start_date": start.isoformat(),
                "end_date": end.isoformat()
            }
        )
    
    @staticmethod
    def _calculate_shift_risk(shift, assignments: List, staff_map: Dict) -> tuple:
        """
        Calculate risk score (0-100) and identify risk factors.
        
        Risk factors:
        - Understaffing: +30 points
        - No supervisor when required: +25 points
        - Skill gaps: +20 points
        - Weekend/night shift: +10 points
        - High priority: +15 points
        """
        score = 0
        factors = []
        
        # Understaffing
        if len(assignments) < shift.min_staff:
            gap = shift.min_staff - len(assignments)
            penalty = min(gap * 15, 30)
            score += penalty
            factors.append(f"Understaffed by {gap} staff")
        
        # Supervisor requirement
        if shift.requires_supervisor:
            has_supervisor = any(
                staff_map.get(a.employee_id, {}).is_supervisor
                for a in assignments
                if a.employee_id in staff_map
            )
            if not has_supervisor:
                score += 25
                factors.append("Missing required supervisor")
        
        # Skill gaps
        if hasattr(shift, 'required_skill_ids') and shift.required_skill_ids:
            assigned_skills = set()
            for assignment in assignments:
                staff = staff_map.get(assignment.employee_id)
                if staff and hasattr(staff, 'skills'):
                    assigned_skills.update(staff.skills.keys())
            
            required_skills = set(shift.required_skill_ids)
            missing_skills = required_skills - assigned_skills
            
            if missing_skills:
                score += min(len(missing_skills) * 10, 20)
                factors.append(f"{len(missing_skills)} required skills missing")
        
        # Weekend/night shift
        if shift.shift_date.weekday() in [5, 6]:  # Weekend
            score += 5
            factors.append("Weekend shift")
        
        if shift.shift_type == "NIGHT":
            score += 10
            factors.append("Night shift")
        
        # High priority
        if shift.priority >= 3:
            score += 15
            factors.append(f"High priority (level {shift.priority})")
        
        if not factors:
            factors.append("No significant risk factors")
        
        return min(100, score), factors
    
    @staticmethod
    def _get_coverage_status(shift, assigned_count: int) -> str:
        """Determine coverage status"""
        if assigned_count < shift.min_staff:
            return "UNDERSTAFFED"
        elif assigned_count > shift.max_staff:
            return "OVERSTAFFED"
        else:
            return "ADEQUATE"
    
    @staticmethod
    def _identify_skill_gaps(shift, assignments: List, staff_map: Dict) -> List[str]:
        """Identify missing skills for a shift"""
        if not hasattr(shift, 'required_skill_ids') or not shift.required_skill_ids:
            return []
        
        assigned_skills = set()
        for assignment in assignments:
            staff = staff_map.get(assignment.employee_id)
            if staff and hasattr(staff, 'skills'):
                assigned_skills.update(staff.skills.keys())
        
        required_skills = set(shift.required_skill_ids)
        missing_skills = required_skills - assigned_skills
        
        return [f"Skill_{sid}" for sid in missing_skills]
    
    @staticmethod
    def _analyze_departments(shifts_by_dept: Dict, dept_map: Dict) -> Dict[str, DepartmentRisk]:
        """Analyze risk at department level"""
        department_risks = {}
        
        for dept_id, dept_shifts in shifts_by_dept.items():
            dept = dept_map.get(dept_id)
            dept_name = dept.name if dept else f"Department {dept_id}"
            
            # Calculate average risk score
            avg_risk = sum(s.risk_score for s in dept_shifts) / len(dept_shifts) if dept_shifts else 0
            
            # Count high-risk shifts (score >= 50)
            high_risk_count = sum(1 for s in dept_shifts if s.risk_score >= 50)
            
            # Calculate coverage rate
            adequate_shifts = sum(1 for s in dept_shifts if s.coverage_status == "ADEQUATE")
            coverage_rate = (adequate_shifts / len(dept_shifts) * 100) if dept_shifts else 100
            
            # Identify primary concerns
            concerns = []
            understaffed = sum(1 for s in dept_shifts if s.coverage_status == "UNDERSTAFFED")
            if understaffed > 0:
                concerns.append(f"{understaffed} understaffed shifts")
            
            missing_supervisors = sum(1 for s in dept_shifts if s.shift_type != "ON_CALL" and not s.has_supervisor)
            if missing_supervisors > 3:
                concerns.append(f"{missing_supervisors} shifts missing supervisors")
            
            shifts_with_skill_gaps = sum(1 for s in dept_shifts if s.skill_gaps)
            if shifts_with_skill_gaps > 0:
                concerns.append(f"{shifts_with_skill_gaps} shifts with skill gaps")
            
            if not concerns:
                concerns.append("No major concerns")
            
            department_risks[dept_name] = DepartmentRisk(
                department_id=dept_id,
                department_name=dept_name,
                risk_score=int(avg_risk),
                high_risk_shifts=high_risk_count,
                coverage_rate=round(coverage_rate, 1),
                primary_concerns=concerns
            )
        
        return department_risks
    
    @staticmethod
    def _load_departments(session: Session, org_id: int) -> List[Department]:
        """Load departments for organization"""
        from sqlmodel import select
        return session.exec(select(Department).where(Department.org_id == org_id)).all()
