# app/services/analytics/recommendation_service.py
"""
Recommendation Analytics Service - Answers: "What would improve the situation most?"

Generates actionable recommendations and scenario analysis.
"""
from datetime import date, timedelta
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session
import uuid

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    RecommendationAnalysis,
    Recommendation,
    ScenarioAnalysis,
    Scenario
)


class RecommendationAnalyticsService:
    """Actionable recommendations and scenario analysis service"""
    
    @staticmethod
    def generate_recommendations(session: Session, org_id: int) -> RecommendationAnalysis:
        """
        Generate actionable recommendations and scenario analysis.
        
        Answers: "What would improve the situation most?"
        """
        # Analyze next 30 days
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
        
        # Load data
        adapter = DBAdapter(session, org_id)
        staff_list = adapter.load_staff()
        shifts = adapter.load_shifts(start_date, end_date)
        
        # Group assignments
        assignments_by_shift = defaultdict(list)
        all_assignments = adapter.load_assignments_bulk(start_date, end_date)
        for assignment in all_assignments:
            assignments_by_shift[assignment.shift_id].append(assignment)
        
        # Generate recommendations
        recommendations = []
        
        # 1. Staffing recommendations
        recommendations.extend(RecommendationAnalyticsService._generate_staffing_recommendations(
            shifts, assignments_by_shift
        ))
        
        # 2. Skill recommendations
        recommendations.extend(RecommendationAnalyticsService._generate_skill_recommendations(
            staff_list
        ))
        
        # 3. Workload recommendations
        recommendations.extend(RecommendationAnalyticsService._generate_workload_recommendations(
            staff_list, all_assignments
        ))
        
        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda r: priority_order[r.priority])
        
        # Generate scenario analysis
        scenario_analysis = RecommendationAnalyticsService._generate_scenarios(
            shifts, assignments_by_shift, staff_list
        )
        
        return RecommendationAnalysis(
            recommendations=recommendations,
            scenario_analysis=scenario_analysis
        )
    
    @staticmethod
    def _generate_staffing_recommendations(shifts: List, assignments_by_shift: Dict) -> List[Recommendation]:
        """Generate staffing-related recommendations"""
        recommendations = []
        
        # Count understaffed shifts
        understaffed = [s for s in shifts if len(assignments_by_shift.get(s.id, [])) < s.min_staff]
        
        if understaffed:
            total_gap = sum(s.min_staff - len(assignments_by_shift.get(s.id, [])) for s in understaffed)
            
            recommendations.append(Recommendation(
                id=str(uuid.uuid4()),
                priority="HIGH",
                category="STAFFING",
                title=f"Address {len(understaffed)} understaffed shifts",
                description=f"Total staffing gap of {total_gap} positions across {len(understaffed)} shifts. Immediate hiring or schedule adjustment needed.",
                impact="Improve operational safety and service quality",
                effort="HIGH",
                estimated_improvement={
                    "coverage_increase": round((total_gap / len(shifts) * 100), 1),
                    "risk_reduction": 25.0
                }
            ))
        
        return recommendations
    
    @staticmethod
    def _generate_skill_recommendations(staff_list: List) -> List[Recommendation]:
        """Generate skill development recommendations"""
        recommendations = []
        
        # Count skills per staff
        skill_counts = defaultdict(int)
        for staff in staff_list:
            if hasattr(staff, 'skills') and staff.skills:
                for skill_id in staff.skills.keys():
                    skill_counts[skill_id] += 1
        
        # Find skills with low coverage (< 3 people)
        low_coverage_skills = [skill for skill, count in skill_counts.items() if count < 3]
        
        if low_coverage_skills:
            recommendations.append(Recommendation(
                id=str(uuid.uuid4()),
                priority="MEDIUM",
                category="SKILLS",
                title=f"Develop {len(low_coverage_skills)} under-represented skills",
                description=f"Skills with fewer than 3 qualified staff create dependency risks. Recommend cross-training programs.",
                impact="Reduce dependency on key staff and improve flexibility",
                effort="MEDIUM",
                estimated_improvement={
                    "dependency_reduction": 30.0,
                    "resilience_increase": 20.0
                }
            ))
        
        return recommendations
    
    @staticmethod
    def _generate_workload_recommendations(staff_list: List, assignments: List) -> List[Recommendation]:
        """Generate workload-related recommendations"""
        recommendations = []
        
        # Count assignments per staff
        assignments_by_staff = defaultdict(int)
        for assignment in assignments:
            assignments_by_staff[assignment.employee_id] += 1
        
        # Find overworked staff (> 20 shifts in 30 days)
        overworked = [
            staff for staff in staff_list
            if assignments_by_staff.get(staff.employee_id, 0) > 20
        ]
        
        if overworked:
            recommendations.append(Recommendation(
                id=str(uuid.uuid4()),
                priority="HIGH",
                category="WORKLOAD",
                title=f"Redistribute workload for {len(overworked)} overworked staff",
                description=f"{len(overworked)} staff members are assigned to more than 20 shifts in 30 days, risking burnout.",
                impact="Prevent burnout and improve staff retention",
                effort="MEDIUM",
                estimated_improvement={
                    "burnout_reduction": 40.0,
                    "fairness_increase": 25.0
                }
            ))
        
        return recommendations
    
    @staticmethod
    def _generate_scenarios(shifts: List, assignments_by_shift: Dict, staff_list: List) -> ScenarioAnalysis:
        """Generate what-if scenario analysis"""
        
        # Calculate current state
        understaffed_count = sum(1 for s in shifts if len(assignments_by_shift.get(s.id, [])) < s.min_staff)
        current_coverage = ((len(shifts) - understaffed_count) / len(shifts) * 100) if shifts else 100
        
        scenarios = []
        
        # Scenario 1: Add staff
        staff_to_add = max(2, understaffed_count // 10)
        scenarios.append(Scenario(
            name="Hire Additional Staff",
            description=f"Add {staff_to_add} new staff members to address coverage gaps",
            actions=[
                f"Recruit {staff_to_add} qualified staff",
                "Onboard and train new hires",
                "Integrate into scheduling rotation"
            ],
            estimated_cost=f"${staff_to_add * 60000}/year (assuming $60k per staff)",
            expected_outcomes={
                "coverage_improvement": f"+{min(15, staff_to_add * 5)}%",
                "burnout_reduction": f"-{min(30, staff_to_add * 10)}%",
                "flexibility": "Increased scheduling flexibility"
            },
            roi_months=6
        ))
        
        # Scenario 2: Adjust constraints
        scenarios.append(Scenario(
            name="Relax Scheduling Constraints",
            description="Adjust shift requirements and constraints to improve coverage",
            actions=[
                "Review and adjust minimum staffing requirements",
                "Allow more flexible shift swapping",
                "Implement on-call rotation for low-priority shifts"
            ],
            estimated_cost="$0 (policy change)",
            expected_outcomes={
                "coverage_improvement": "+5-10%",
                "staff_satisfaction": "May decrease slightly",
                "operational_flexibility": "Significantly increased"
            },
            roi_months=1
        ))
        
        # Scenario 3: Cross-training
        scenarios.append(Scenario(
            name="Implement Cross-Training Program",
            description="Train staff in multiple skills to increase coverage flexibility",
            actions=[
                "Identify skill gaps and training needs",
                "Develop training curriculum",
                "Schedule training sessions",
                "Certify staff in new skills"
            ],
            estimated_cost="$5,000-10,000 for training materials and time",
            expected_outcomes={
                "skill_redundancy": "+40%",
                "dependency_risk": "-35%",
                "scheduling_flexibility": "Significantly improved"
            },
            roi_months=3
        ))
        
        return ScenarioAnalysis(scenarios=scenarios)
