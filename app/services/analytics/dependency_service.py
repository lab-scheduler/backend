# app/services/analytics/dependency_service.py
"""
Dependency Analytics Service - Answers: "Are we relying too heavily on key staff?"

Identifies key staff dependencies, bus factor, and skill concentration risks.
"""
from datetime import date, timedelta
from typing import List, Dict
from collections import defaultdict, Counter
from sqlmodel import Session

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    DependencyAnalysis,
    KeyStaffDependency,
    SkillDependency
)


class DependencyAnalyticsService:
    """Key staff and skill dependency analysis service"""
    
    @staticmethod
    def analyze_dependencies(session: Session, org_id: int, period_days: int = 30) -> DependencyAnalysis:
        """
        Comprehensive dependency analysis.
        
        Answers: "Are we relying too heavily on a small group of people?"
        """
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        # Load data
        adapter = DBAdapter(session, org_id)
        staff_list = adapter.load_staff()
        shifts = adapter.load_shifts(start_date, end_date)
        
        # Build shift map
        shift_map = {s.id: s for s in shifts}
        
        # Group assignments by staff
        assignments_by_staff = defaultdict(list)
        all_assignments = adapter.load_assignments_bulk(start_date, end_date)
        for assignment in all_assignments:
            assignments_by_staff[assignment.employee_id].append(assignment)
        
        total_shifts = len(shifts)
        
        # Analyze key staff
        key_staff = DependencyAnalyticsService._identify_key_staff(
            staff_list, assignments_by_staff, total_shifts, shift_map
        )
        
        # Analyze skill dependencies
        skill_dependencies = DependencyAnalyticsService._analyze_skill_dependencies(
            staff_list
        )
        
        # Calculate bus factor
        bus_factor = DependencyAnalyticsService._calculate_bus_factor(
            key_staff, skill_dependencies
        )
        
        # Calculate overall concentration risk
        concentration_risk = DependencyAnalyticsService._calculate_concentration_risk(
            key_staff, total_shifts
        )
        
        return DependencyAnalysis(
            key_staff=key_staff,
            bus_factor=bus_factor,
            skill_dependencies=skill_dependencies,
            concentration_risk=concentration_risk
        )
    
    @staticmethod
    def _identify_key_staff(staff_list: List, assignments_by_staff: Dict, 
                           total_shifts: int, shift_map: Dict) -> List[KeyStaffDependency]:
        """Identify staff members who are critical to operations"""
        key_staff = []
        
        for staff in staff_list:
            staff_assignments = assignments_by_staff.get(staff.employee_id, [])
            
            if not staff_assignments:
                continue
            
            # Calculate shift percentage
            shift_percentage = (len(staff_assignments) / total_shifts * 100) if total_shifts > 0 else 0
            
            # Identify unique skills (skills only this person has)
            unique_skills = DependencyAnalyticsService._find_unique_skills(
                staff, staff_list
            )
            
            # Identify critical roles
            critical_roles = []
            if staff.is_supervisor:
                critical_roles.append("Supervisor")
            
            # Check if assigned to high-priority shifts
            high_priority_count = sum(
                1 for a in staff_assignments
                if a.shift_id in shift_map and shift_map[a.shift_id].priority >= 3
            )
            if high_priority_count > 5:
                critical_roles.append(f"High-priority shifts ({high_priority_count})")
            
            # Calculate dependency score
            dependency_score = DependencyAnalyticsService._calculate_dependency_score(
                shift_percentage, unique_skills, critical_roles, staff.is_supervisor
            )
            
            # Only include if dependency score is significant (>= 30)
            if dependency_score >= 30:
                # Assess impact if unavailable
                impact = DependencyAnalyticsService._assess_impact(
                    dependency_score, unique_skills, critical_roles
                )
                
                key_staff.append(KeyStaffDependency(
                    employee_id=staff.employee_id,
                    full_name=staff.name,
                    dependency_score=dependency_score,
                    shift_percentage=round(shift_percentage, 1),
                    unique_skills=unique_skills,
                    critical_roles=critical_roles,
                    impact_if_unavailable=impact
                ))
        
        # Sort by dependency score (highest first)
        key_staff.sort(key=lambda x: x.dependency_score, reverse=True)
        
        return key_staff
    
    @staticmethod
    def _find_unique_skills(staff, all_staff: List) -> List[str]:
        """Find skills that only this staff member has"""
        if not hasattr(staff, 'skills') or not staff.skills:
            return []
        
        staff_skills = set(staff.skills.keys())
        unique_skills = []
        
        for skill_id in staff_skills:
            # Check if any other staff has this skill
            others_with_skill = sum(
                1 for other in all_staff
                if other.employee_id != staff.employee_id
                and hasattr(other, 'skills')
                and skill_id in other.skills
            )
            
            if others_with_skill == 0:
                unique_skills.append(f"Skill_{skill_id}")
        
        return unique_skills
    
    @staticmethod
    def _calculate_dependency_score(shift_percentage: float, unique_skills: List,
                                    critical_roles: List, is_supervisor: bool) -> int:
        """
        Calculate dependency score (0-100).
        
        Scoring:
        - Shift percentage: up to 40 points (1 point per 2.5%)
        - Unique skills: +15 points per unique skill (max 30)
        - Supervisor: +20 points
        - Critical roles: +5 points per role (max 10)
        """
        score = 0
        
        # Shift percentage contribution
        score += min(int(shift_percentage / 2.5), 40)
        
        # Unique skills
        score += min(len(unique_skills) * 15, 30)
        
        # Supervisor bonus
        if is_supervisor:
            score += 20
        
        # Critical roles
        score += min(len(critical_roles) * 5, 10)
        
        return min(100, score)
    
    @staticmethod
    def _assess_impact(dependency_score: int, unique_skills: List, critical_roles: List) -> str:
        """Assess the impact if this person becomes unavailable"""
        if dependency_score >= 70:
            return "CRITICAL - Operations would be severely impacted"
        elif dependency_score >= 50:
            if unique_skills:
                return f"HIGH - Loss of unique skills: {', '.join(unique_skills)}"
            else:
                return "HIGH - Significant coverage gaps would occur"
        elif dependency_score >= 30:
            return "MEDIUM - Workload redistribution required"
        else:
            return "LOW - Minimal impact"
    
    @staticmethod
    def _analyze_skill_dependencies(staff_list: List) -> List[SkillDependency]:
        """Analyze dependency on specific skills"""
        # Count staff per skill
        skill_counts = defaultdict(lambda: {"total": 0, "expert": 0})
        
        for staff in staff_list:
            if not hasattr(staff, 'skills') or not staff.skills:
                continue
            
            for skill_id, level in staff.skills.items():
                skill_counts[skill_id]["total"] += 1
                
                # Count experts (ADVANCED or EXPERT level)
                if isinstance(level, str) and level.upper() in ["ADVANCED", "EXPERT"]:
                    skill_counts[skill_id]["expert"] += 1
        
        # Create skill dependencies
        skill_dependencies = []
        
        for skill_id, counts in skill_counts.items():
            total = counts["total"]
            experts = counts["expert"]
            
            # Single point of failure if only 1 person has the skill
            spof = (total == 1)
            
            # Determine risk level
            if spof:
                risk_level = "HIGH"
            elif total <= 2:
                risk_level = "HIGH"
            elif total <= 4:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            skill_dependencies.append(SkillDependency(
                skill_id=skill_id,
                skill_name=f"Skill_{skill_id}",
                total_staff_with_skill=total,
                expert_count=experts,
                single_point_of_failure=spof,
                risk_level=risk_level
            ))
        
        # Sort by risk (HIGH first, then by total staff ascending)
        risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        skill_dependencies.sort(key=lambda x: (risk_order[x.risk_level], x.total_staff_with_skill))
        
        return skill_dependencies
    
    @staticmethod
    def _calculate_bus_factor(key_staff: List[KeyStaffDependency], 
                              skill_dependencies: List[SkillDependency]) -> int:
        """
        Calculate bus factor: minimum number of people who could leave before crisis.
        
        This is the minimum of:
        - Number of people with unique skills
        - Number of high-dependency staff (score >= 70)
        """
        # Count staff with unique skills
        staff_with_unique_skills = sum(1 for s in key_staff if s.unique_skills)
        
        # Count high-dependency staff
        high_dependency_staff = sum(1 for s in key_staff if s.dependency_score >= 70)
        
        # Count single points of failure in skills
        skill_spof = sum(1 for s in skill_dependencies if s.single_point_of_failure)
        
        # Bus factor is the minimum (most critical constraint)
        bus_factor = min(
            staff_with_unique_skills if staff_with_unique_skills > 0 else 999,
            high_dependency_staff if high_dependency_staff > 0 else 999,
            skill_spof if skill_spof > 0 else 999
        )
        
        # If no critical dependencies, return a reasonable number
        if bus_factor == 999:
            bus_factor = max(3, len(key_staff) // 3)
        
        return max(1, bus_factor)
    
    @staticmethod
    def _calculate_concentration_risk(key_staff: List[KeyStaffDependency], 
                                     total_shifts: int) -> int:
        """
        Calculate overall concentration risk score (0-100).
        
        Based on:
        - Top 3 staff shift percentage
        - Number of high-dependency staff
        - Average dependency score
        """
        if not key_staff:
            return 0
        
        # Top 3 staff concentration
        top_3_percentage = sum(s.shift_percentage for s in key_staff[:3])
        concentration_score = min(int(top_3_percentage / 2), 40)
        
        # High-dependency staff count
        high_dep_count = sum(1 for s in key_staff if s.dependency_score >= 70)
        concentration_score += min(high_dep_count * 15, 30)
        
        # Average dependency score
        avg_dependency = sum(s.dependency_score for s in key_staff) / len(key_staff)
        concentration_score += min(int(avg_dependency / 3), 30)
        
        return min(100, concentration_score)
