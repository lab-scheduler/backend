# app/services/analytics/safety_service.py
"""
Safety Analytics Service - Answers: "Is the hospital/lab operationally safe today?"

Provides comprehensive safety assessment including:
- Overall coverage rates
- Supervisor coverage (FIXED - no longer placeholder)
- Skill coverage per shift (FIXED - no longer placeholder)
- Critical gaps identification
- Safety scoring with thresholds
"""
from datetime import date
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    SafetyAnalysis,
    CriticalGap
)
from app.db.models import Department


class SafetyAnalyticsService:
    """Operational safety analysis service"""
    
    @staticmethod
    def analyze_safety(session: Session, org_id: int, start: date, end: date) -> SafetyAnalysis:
        """
        Comprehensive safety analysis for the specified period.
        
        Answers the critical question: "Is the hospital/lab operationally safe today?"
        """
        # Load data
        adapter = DBAdapter(session, org_id)
        shifts = adapter.load_shifts(start, end)
        staff_list = adapter.load_staff()
        departments = SafetyAnalyticsService._load_departments(session, org_id)
        
        # Build lookups
        dept_map = {d.id: d for d in departments}
        staff_map = {s.employee_id: s for s in staff_list}
        
        # Group assignments by shift
        assignments_by_shift = defaultdict(list)
        all_assignments = adapter.load_assignments_bulk(start, end)
        for assignment in all_assignments:
            assignments_by_shift[assignment.shift_id].append(assignment)
        
        # Calculate coverage metrics
        coverage_rate = SafetyAnalyticsService._calculate_coverage_rate(
            shifts, assignments_by_shift
        )
        
        # FIXED: Calculate actual supervisor coverage (was placeholder)
        supervisor_coverage_rate = SafetyAnalyticsService._calculate_supervisor_coverage(
            shifts, assignments_by_shift, staff_map
        )
        
        # FIXED: Calculate actual skill coverage (was placeholder)
        skill_coverage_rate = SafetyAnalyticsService._calculate_skill_coverage(
            shifts, assignments_by_shift, staff_map
        )
        
        # Identify critical gaps
        critical_gaps = SafetyAnalyticsService._identify_critical_gaps(
            shifts, assignments_by_shift, staff_map, dept_map
        )
        
        # Calculate safety score
        safety_score = SafetyAnalyticsService._calculate_safety_score(
            coverage_rate, supervisor_coverage_rate, skill_coverage_rate, len(critical_gaps)
        )
        
        # Determine safety status
        status = SafetyAnalyticsService._get_safety_status(safety_score)
        
        return SafetyAnalysis(
            safety_score=safety_score,
            status=status,
            coverage_rate=round(coverage_rate, 1),
            minimum_requirements_met=len(critical_gaps) == 0,
            supervisor_coverage_rate=round(supervisor_coverage_rate, 1),
            skill_coverage_rate=round(skill_coverage_rate, 1),
            critical_gaps=critical_gaps,
            period={
                "start_date": start.isoformat(),
                "end_date": end.isoformat()
            }
        )
    
    @staticmethod
    def _calculate_coverage_rate(shifts: List, assignments_by_shift: Dict) -> float:
        """Calculate percentage of shifts meeting minimum staffing"""
        if not shifts:
            return 100.0
        
        covered = sum(
            1 for shift in shifts
            if len(assignments_by_shift.get(shift.id, [])) >= shift.min_staff
        )
        
        return (covered / len(shifts)) * 100
    
    @staticmethod
    def _calculate_supervisor_coverage(shifts: List, assignments_by_shift: Dict, staff_map: Dict) -> float:
        """
        FIXED: Calculate actual supervisor coverage (previously placeholder at 100%)
        
        Returns percentage of supervisor-required shifts that have a supervisor assigned.
        """
        supervisor_required_shifts = [s for s in shifts if s.requires_supervisor]
        
        if not supervisor_required_shifts:
            return 100.0  # No supervisor requirements, so 100% covered
        
        covered = 0
        for shift in supervisor_required_shifts:
            shift_assignments = assignments_by_shift.get(shift.id, [])
            # Check if any assigned staff is a supervisor
            has_supervisor = any(
                staff_map.get(assignment.employee_id, {}).is_supervisor
                for assignment in shift_assignments
                if assignment.employee_id in staff_map
            )
            if has_supervisor:
                covered += 1
        
        return (covered / len(supervisor_required_shifts)) * 100
    
    @staticmethod
    def _calculate_skill_coverage(shifts: List, assignments_by_shift: Dict, staff_map: Dict) -> float:
        """
        FIXED: Calculate actual skill coverage per shift (previously placeholder)
        
        Returns percentage of shifts where all required skills are covered.
        """
        if not shifts:
            return 100.0
        
        shifts_with_skill_requirements = [s for s in shifts if hasattr(s, 'required_skill_ids') and s.required_skill_ids]
        
        if not shifts_with_skill_requirements:
            return 100.0  # No skill requirements
        
        covered = 0
        for shift in shifts_with_skill_requirements:
            shift_assignments = assignments_by_shift.get(shift.id, [])
            
            # Get all skills from assigned staff
            assigned_skills = set()
            for assignment in shift_assignments:
                staff = staff_map.get(assignment.employee_id)
                if staff and hasattr(staff, 'skills'):
                    assigned_skills.update(staff.skills.keys())
            
            # Check if all required skills are covered
            required_skills = set(shift.required_skill_ids)
            if required_skills.issubset(assigned_skills):
                covered += 1
        
        return (covered / len(shifts_with_skill_requirements)) * 100
    
    @staticmethod
    def _identify_critical_gaps(shifts: List, assignments_by_shift: Dict, staff_map: Dict, dept_map: Dict) -> List[CriticalGap]:
        """Identify shifts with critical staffing gaps"""
        gaps = []
        
        for shift in shifts:
            assigned = assignments_by_shift.get(shift.id, [])
            assigned_count = len(assigned)
            
            if assigned_count < shift.min_staff:
                gap_size = shift.min_staff - assigned_count
                
                # Check supervisor presence
                has_supervisor = any(
                    staff_map.get(a.employee_id, {}).is_supervisor
                    for a in assigned
                    if a.employee_id in staff_map
                )
                
                # Check missing skills
                missing_skills = []
                if hasattr(shift, 'required_skill_ids') and shift.required_skill_ids:
                    assigned_skills = set()
                    for assignment in assigned:
                        staff = staff_map.get(assignment.employee_id)
                        if staff and hasattr(staff, 'skills'):
                            assigned_skills.update(staff.skills.keys())
                    
                    required_skills = set(shift.required_skill_ids)
                    missing_skill_ids = required_skills - assigned_skills
                    missing_skills = [f"Skill_{sid}" for sid in missing_skill_ids]
                
                # Determine severity
                severity = "HIGH" if gap_size >= 2 or (shift.requires_supervisor and not has_supervisor) else "MEDIUM"
                if gap_size == 1 and has_supervisor:
                    severity = "LOW"
                
                dept = dept_map.get(shift.department_id)
                
                gaps.append(CriticalGap(
                    shift_id=shift.id,
                    date=shift.shift_date,
                    shift_type=shift.shift_type,
                    department_name=dept.name if dept else f"Dept {shift.department_id}",
                    department_id=shift.department_id,
                    required_staff=shift.min_staff,
                    assigned_staff=assigned_count,
                    gap=gap_size,
                    severity=severity,
                    has_supervisor=has_supervisor,
                    missing_skills=missing_skills
                ))
        
        # Sort by severity and gap size
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        gaps.sort(key=lambda g: (severity_order[g.severity], -g.gap))
        
        return gaps
    
    @staticmethod
    def _calculate_safety_score(coverage_rate: float, supervisor_coverage: float, 
                                skill_coverage: float, gap_count: int) -> int:
        """
        Calculate overall safety score (0-100) based on multiple factors.
        
        Scoring:
        - Coverage rate: 50% weight
        - Supervisor coverage: 25% weight
        - Skill coverage: 15% weight
        - Gap penalty: -2 points per critical gap (10% weight)
        """
        score = (
            (coverage_rate * 0.50) +
            (supervisor_coverage * 0.25) +
            (skill_coverage * 0.15) +
            (10 * 1.0)  # Base 10 points
        )
        
        # Penalty for critical gaps
        gap_penalty = min(gap_count * 2, 20)  # Max 20 point penalty
        score -= gap_penalty
        
        return max(0, min(100, int(score)))
    
    @staticmethod
    def _get_safety_status(safety_score: int) -> str:
        """
        FIXED: Determine safety status based on score thresholds.
        
        Thresholds:
        - SAFE: >= 90
        - CAUTION: 70-89
        - CRITICAL: < 70
        """
        if safety_score >= 90:
            return "SAFE"
        elif safety_score >= 70:
            return "CAUTION"
        else:
            return "CRITICAL"
    
    @staticmethod
    def _load_departments(session: Session, org_id: int) -> List[Department]:
        """Load departments for organization"""
        from sqlmodel import select
        return session.exec(select(Department).where(Department.org_id == org_id)).all()
