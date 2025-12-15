# app/services/enhanced_analysis_service.py
from datetime import date, datetime
from typing import List, Dict, Any
from collections import defaultdict
import statistics
from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.scheduler_engine.core.scoring_engine import ScoringEngine
from app.scheduler_engine.core.greedy_engine import GreedyEngine
from app.db.models import Staff, Department, Shift, ShiftAssignment

class EnhancedAnalysisService:
    """Enhanced analysis service with comprehensive reporting capabilities"""

    @staticmethod
    def get_comprehensive_analysis(session, org_id: int, start: date, end: date):
        """Generate comprehensive analysis with full details - optimized version"""
        # Load all necessary data with optimized queries
        adapter = DBAdapter(session, org_id)
        staff_list = adapter.load_staff()
        shifts = adapter.load_shifts(start, end)
        departments = EnhancedAnalysisService._load_departments(session, org_id)
        assignments = EnhancedAnalysisService._load_assignments(session, org_id, start, end)

        # Pre-compute lookups for performance
        staff_map = {s.employee_id: s for s in staff_list}
        dept_map = {d.id: d for d in departments}
        shift_map = {s.id: s for s in shifts}

        # Pre-group assignments by shift and staff for O(1) lookups
        assignments_by_shift = {}
        assignments_by_staff = {}
        for assignment in assignments:
            if assignment.shift_id not in assignments_by_shift:
                assignments_by_shift[assignment.shift_id] = []
            assignments_by_shift[assignment.shift_id].append(assignment)

            if assignment.employee_id not in assignments_by_staff:
                assignments_by_staff[assignment.employee_id] = []
            assignments_by_staff[assignment.employee_id].append(assignment)

        # Pre-group shifts by department
        shifts_by_dept = {}
        for shift in shifts:
            if shift.department_id not in shifts_by_dept:
                shifts_by_dept[shift.department_id] = []
            shifts_by_dept[shift.department_id].append(shift)

        # Build engine for analysis
        engine = GreedyEngine()
        for s in staff_list:
            engine.add_staff(s)
        for sh in shifts:
            engine.add_shift(sh)

        # Run analysis
        scorer = ScoringEngine()

        # Generate comprehensive report using pre-computed data
        report = {
            "meta": EnhancedAnalysisService._generate_meta(org_id, start, end),
            "executive_summary": EnhancedAnalysisService._generate_summary_optimized(
                shifts, assignments, departments, assignments_by_shift, shift_map
            ),
            "departments": EnhancedAnalysisService._analyze_departments_optimized(
                departments, shifts_by_dept, assignments_by_shift, staff_map, dept_map
            ),
            "staff_details": EnhancedAnalysisService._analyze_staff_optimized(
                staff_list, assignments_by_staff, shift_map, dept_map
            ),
            "shifts": EnhancedAnalysisService._detail_shifts_optimized(
                shifts, assignments_by_shift, dept_map, staff_map
            ),
            "analytics": EnhancedAnalysisService._calculate_analytics_optimized(
                shifts, assignments, staff_list, departments, assignments_by_shift
            ),
            "recommendations": EnhancedAnalysisService._generate_recommendations_optimized(
                shifts, assignments_by_shift, departments, shift_map
            )
        }

        return {"ok": True, "report": report}

    @staticmethod
    def _generate_meta(org_id: int, start: date, end: date) -> Dict:
        """Generate metadata for the report"""
        return {
            "organization": {"id": org_id},
            "period": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "total_days": (end - start).days + 1
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "engine_used": "greedy",
            "analysis_version": "2.0"
        }

    @staticmethod
    def _generate_summary(shifts: List, assignments: List, departments: List) -> Dict:
        """Generate executive summary"""
        total_shifts = len(shifts)
        total_staff = len(set(a.employee_id for a in assignments))
        departments_count = len(departments)

        # Coverage calculation
        shift_coverage = {}
        for shift in shifts:
            assigned = [a for a in assignments if a.shift_id == shift.id]
            shift_coverage[shift.id] = len(assigned) >= shift.min_staff

        fully_covered = sum(shift_coverage.values())
        coverage_rate = (fully_covered / total_shifts * 100) if total_shifts else 0

        # Calculate total hours (assuming 8 hours per shift)
        total_hours = len(assignments) * 8
        estimated_cost = total_hours * 25  # Assuming $25/hour average

        # Issues identification
        critical_issues = []
        if coverage_rate < 90:
            critical_issues.append(f"Low overall coverage rate: {coverage_rate:.1f}%")

        # Key insights
        insights = []
        if total_shifts > 0:
            day_shifts = [s for s in shifts if s.shift_type == "DAY"]
            night_shifts = [s for s in shifts if s.shift_type == "NIGHT"]

            if day_shifts and night_shifts:
                day_coverage = sum(shift_coverage[s.id] for s in day_shifts) / len(day_shifts) * 100
                night_coverage = sum(shift_coverage[s.id] for s in night_shifts) / len(night_shifts) * 100
                insights.append(f"Day shifts have {day_coverage:.1f}% coverage vs {night_coverage:.1f}% for nights")

        return {
            "total_shifts": total_shifts,
            "total_staff": total_staff,
            "departments_count": departments_count,
            "overall_coverage_rate": round(coverage_rate, 1),
            "total_scheduled_hours": total_hours,
            "estimated_cost": estimated_cost,
            "average_utilization": round((total_hours / (total_staff * 40)) * 100, 1) if total_staff > 0 else 0,
            "quality_score": min(100, coverage_rate + 10),
            "critical_issues": critical_issues,
            "key_insights": insights
        }

    @staticmethod
    def _analyze_departments(departments: List, shifts: List, assignments: List, staff_list: List) -> List[Dict]:
        """Analyze each department in detail"""
        dept_analysis = []

        for dept in departments:
            dept_shifts = [s for s in shifts if s.department_id == dept.id]
            dept_assignments = [a for a in assignments if any(s.department_id == dept.id for s in shifts if s.id == a.shift_id)]

            # Coverage by shift type
            shifts_by_type = defaultdict(list)
            for shift in dept_shifts:
                shifts_by_type[shift.shift_type].append(shift)

            coverage_by_type = {}
            for shift_type, type_shifts in shifts_by_type.items():
                covered = sum(1 for s in type_shifts
                            if len([a for a in assignments if a.shift_id == s.id]) >= s.min_staff)
                coverage_by_type[shift_type] = {
                    "total": len(type_shifts),
                    "covered": covered,
                    "rate": round((covered / len(type_shifts)) * 100, 1) if type_shifts else 100
                }

            # Staff metrics
            assigned_staff_ids = set(a.employee_id for a in dept_assignments)
            dept_staff = [s for s in staff_list if s.employee_id in assigned_staff_ids]

            avg_shifts = len(dept_assignments) / len(dept_staff) if dept_staff else 0
            utilization = round((len(dept_assignments) * 8) / (len(dept_staff) * 40) * 100, 1) if dept_staff else 0

            dept_analysis.append({
                "department_id": dept.id,
                "name": dept.name,
                "shifts": {
                    "total": len(dept_shifts),
                    "fully_covered": sum(1 for s in dept_shifts
                                       if len([a for a in assignments if a.shift_id == s.id]) >= s.min_staff),
                    "coverage_rate": round(
                        (sum(1 for s in dept_shifts
                            if len([a for a in assignments if a.shift_id == s.id]) >= s.min_staff) /
                         len(dept_shifts)) * 100, 1) if dept_shifts else 100,
                    "by_type": coverage_by_type
                },
                "staff": {
                    "assigned_count": len(dept_staff),
                    "average_shifts_per_staff": round(avg_shifts, 1),
                    "utilization_rate": utilization,
                    "supervisor_coverage": 100,  # Placeholder - would need actual supervisor data
                    "skill_gaps": []  # Placeholder - would need skill analysis
                },
                "metrics": {
                    "total_hours": len(dept_assignments) * 8,
                    "estimated_cost": len(dept_assignments) * 8 * 25,
                    "avg_score": 85.5,  # Placeholder - would calculate actual scores
                    "overtime_shifts": 0,  # Placeholder - would need overtime tracking
                    "consecutive_day_violations": 0  # Placeholder - would need consecutive tracking
                }
            })

        return dept_analysis

    @staticmethod
    def _analyze_staff(staff_list: List, assignments: List, shifts: List) -> List[Dict]:
        """Analyze each staff member in detail"""
        staff_analysis = []

        for staff in staff_list:
            staff_assignments = [a for a in assignments if a.employee_id == staff.employee_id]
            staff_shifts = [s for s in shifts if s.id in [a.shift_id for a in staff_assignments]]

            # Shift type distribution
            shifts_by_type = defaultdict(int)
            for shift in staff_shifts:
                shifts_by_type[shift.shift_type] += 1

            total_hours = len(staff_assignments) * 8
            overtime_hours = max(0, total_hours - 40)  # Assuming 40 hour work week

            # Skills analysis
            # Get skill IDs from assigned shifts
            assigned_skill_ids = set()
            for shift in staff_shifts:
                assigned_skill_ids.update(shift.required_skill_ids)

            # Analyze skills
            proficient_skills = []
            for skill_id, level in staff.skills.items():
                proficient_skills.append(f"Skill_{skill_id}_L{level}")

            utilized_skills = []
            underutilized_skills = []
            for skill_id in staff.skills:
                if skill_id in assigned_skill_ids:
                    utilized_skills.append(f"Skill_{skill_id}")
                else:
                    underutilized_skills.append(f"Skill_{skill_id}")

            skill_match_rate = (len(utilized_skills) / len(staff.skills) * 100) if staff.skills else 0

            skills = {
                "proficient": proficient_skills,
                "utilized": utilized_skills,
                "underutilized": underutilized_skills,
                "skill_match_rate": round(skill_match_rate, 1)
            }

            # Preferences (placeholder - would need actual preference data)
            preferences = {
                "preferred_shifts": ["DAY"],
                "preferred_percentage": 40,
                "actual_percentage": (shifts_by_type.get("DAY", 0) / len(staff_shifts) * 100) if staff_shifts else 0,
                "satisfaction_score": 100
            }

            # Generate recommendations based on analysis
            recommendations = EnhancedAnalysisService._generate_staff_recommendations(
                staff, staff_shifts, total_hours, underutilized_skills, overtime_hours
            )

            staff_analysis.append({
                "employee_id": staff.employee_id,
                "full_name": staff.name,
                "role": staff.role,
                "department": {
                    "id": staff.org_id,
                    "name": f"Department {staff.org_id}"  # Would need actual department lookup
                },
                "assignments": {
                    "total_shifts": len(staff_shifts),
                    "total_hours": total_hours,
                    "by_type": dict(shifts_by_type),
                    "consecutive_days": 0,  # Would need consecutive day calculation
                    "weekends_worked": 0,  # Would need weekend calculation
                    "overtime_hours": overtime_hours
                },
                "skills": skills,
                "preferences": preferences,
                "performance": {
                    "avg_assignment_score": 78.5,  # Placeholder
                    "supervisor_assignments": 0,  # Would need supervisor flag
                    "critical_shifts": 0,  # Would need priority tracking
                    "recommendations": recommendations
                }
            })

        return staff_analysis

    @staticmethod
    def _detail_shifts(shifts: List, assignments: List, departments: List, staff_list: List) -> List[Dict]:
        """Provide detailed information for each shift"""
        detailed_shifts = []

        # Create lookup dictionaries
        dept_map = {d.id: d for d in departments}
        staff_map = {s.employee_id: s for s in staff_list}

        for shift in shifts:
            shift_assignments = [a for a in assignments if a.shift_id == shift.id]
            assigned_staff = []

            for assignment in shift_assignments:
                staff = staff_map.get(assignment.employee_id)
                if staff:
                    assigned_staff.append({
                        "employee_id": staff.employee_id,
                        "full_name": staff.name,
                        "role": staff.role,
                        "is_supervisor": False,  # Would need actual supervisor flag
                        "assigned_hours": 8,  # Assuming 8 hours
                        "match_score": 85,  # Placeholder
                        "skills_matched": []  # Would need actual skill matching
                    })

            coverage_status = "ADEQUATE"
            if len(assigned_staff) < shift.min_staff:
                coverage_status = "UNDERSTAFFED"
            elif len(assigned_staff) > shift.max_staff:
                coverage_status = "OVERSTAFFED"

            detailed_shifts.append({
                "shift_id": shift.id,
                "date": shift.shift_date.isoformat(),
                "type": shift.shift_type,
                "department": {
                    "id": shift.department_id,
                    "name": dept_map.get(shift.department_id, {}).name if dept_map.get(shift.department_id) else f"Dept {shift.department_id}"
                },
                "requirements": {
                    "min_staff": shift.min_staff,
                    "max_staff": shift.max_staff,
                    "requires_supervisor": False,  # Would need actual flag
                    "required_skills": [],  # Would need skill requirements
                    "priority": getattr(shift, 'priority', 1),
                    "hours": getattr(shift, 'hours', 8)
                },
                "assignments": assigned_staff,
                "coverage": {
                    "assigned_count": len(assigned_staff),
                    "meets_minimum": len(assigned_staff) >= shift.min_staff,
                    "coverage_status": coverage_status,
                    "skill_coverage": {}  # Would need skill coverage analysis
                },
                "metrics": {
                    "total_score": 82.5,  # Placeholder
                    "estimated_cost": len(assigned_staff) * 8 * 25,
                    "utilization_rate": round((len(assigned_staff) / shift.max_staff) * 100, 1) if shift.max_staff > 0 else 0
                }
            })

        return detailed_shifts

    @staticmethod
    def _calculate_analytics(shifts: List, assignments: List, staff_list: List, departments: List) -> Dict:
        """Calculate advanced analytics metrics"""
        # Fairness metrics
        shifts_per_staff = defaultdict(int)
        for assignment in assignments:
            shifts_per_staff[assignment.employee_id] += 1

        if len(shifts_per_staff) > 1:
            shift_variance = statistics.variance(list(shifts_per_staff.values()))
        else:
            shift_variance = 0

        # Skill analysis (placeholder)
        skill_analysis = {
            "overall_coverage": 89.2,
            "critical_gaps": [],
            "surplus_skills": []
        }

        # Cost analysis
        total_hours = len(assignments) * 8
        estimated_cost = total_hours * 25
        overtime_cost = sum(max(0, shifts_per_staff[emp] * 8 - 40) * 37.5 for emp in shifts_per_staff)  # Time and a half for overtime

        return {
            "fairness_metrics": {
                "shift_distribution_variance": round(shift_variance, 2),
                "hour_distribution_variance": round(shift_variance * 64, 2),  # 8 hours per shift
                "weekend_distribution_score": 78.5  # Placeholder
            },
            "skill_analysis": skill_analysis,
            "cost_analysis": {
                "total_estimated_cost": estimated_cost,
                "cost_per_shift": round(estimated_cost / len(shifts), 2) if shifts else 0,
                "cost_per_hour": 25,
                "overtime_cost": overtime_cost,
                "optimization_potential": round(estimated_cost * 0.05, 2)  # Assume 5% optimization potential
            },
            "quality_metrics": {
                "preference_satisfaction": 76.5,  # Placeholder
                "skill_utilization": 82.3,  # Placeholder
                "supervisor_coverage": 100,  # Placeholder
                "continuity_score": 85.7  # Placeholder
            },
            "trends": {
                "coverage_trend": "STABLE",
                "utilization_trend": "INCREASING",
                "issue_areas": []  # Would need historical data
            }
        }

    @staticmethod
    def _generate_recommendations(shifts: List, assignments: List, departments: List) -> Dict:
        """Generate actionable recommendations"""
        recommendations = {
            "immediate_actions": [],
            "skill_development": [],
            "optimization_opportunities": []
        }

        # Check for understaffed shifts
        understaffed_by_dept = defaultdict(int)
        for shift in shifts:
            assigned = [a for a in assignments if a.shift_id == shift.id]
            if len(assigned) < shift.min_staff:
                understaffed_by_dept[shift.department_id] += 1

        for dept_id, count in understaffed_by_dept.items():
            if count > 0:
                recommendations["immediate_actions"].append({
                    "priority": "HIGH",
                    "category": "STAFFING",
                    "description": f"Department {dept_id} has {count} understaffed shifts",
                    "impact": "Improve coverage and service quality"
                })

        # Overtime recommendations
        shifts_per_staff = defaultdict(int)
        for assignment in assignments:
            shifts_per_staff[assignment.employee_id] += 1

        for emp_id, shifts_count in shifts_per_staff.items():
            hours = shifts_count * 8
            if hours > 45:  # More than 5 hours overtime
                recommendations["immediate_actions"].append({
                    "priority": "MEDIUM",
                    "category": "WORKLOAD",
                    "description": f"Staff {emp_id} has {hours - 40} overtime hours",
                    "impact": "Prevent burnout and reduce overtime costs"
                })

        # Optimization opportunities
        recommendations["optimization_opportunities"].append({
            "area": "Shift Distribution",
            "potential_savings": "$1000/month",
            "implementation": "Balance workload across staff members"
        })

        return recommendations

    @staticmethod
    def _load_departments(session, org_id: int) -> List[Department]:
        """Load departments for organization"""
        from sqlmodel import select
        return session.exec(select(Department).where(Department.org_id == org_id)).all()

    @staticmethod
    def _load_assignments(session, org_id: int, start: date, end: date) -> List[ShiftAssignment]:
        """Load shift assignments efficiently using optimized adapter"""
        from app.scheduler_engine.adapters.db_adapter import DBAdapter
        adapter = DBAdapter(session, org_id)
        return adapter.load_assignments_bulk(start, end)

    @staticmethod
    def _generate_staff_recommendations(staff, staff_shifts, total_hours, underutilized_skills, overtime_hours):
        """Generate personalized recommendations for staff member"""
        recommendations = []

        # Overtime recommendations
        if overtime_hours > 0:
            recommendations.append({
                "type": "WORKLOAD",
                "priority": "HIGH",
                "message": f"Consider reducing workload by {overtime_hours} hours to avoid burnout"
            })

        # Skills recommendations
        if underutilized_skills:
            recommendations.append({
                "type": "SKILLS",
                "priority": "MEDIUM",
                "message": f"Consider utilizing your skills: {', '.join(underutilized_skills[:3])}"
            })

        # Shift type balance
        shift_types = [s.shift_type for s in staff_shifts]
        if len(shift_types) > 0:
            night_shifts = len([t for t in shift_types if t == "NIGHT"])
            if night_shifts > len(shift_types) * 0.4:
                recommendations.append({
                    "type": "SCHEDULE",
                    "priority": "MEDIUM",
                    "message": "You have a high proportion of night shifts. Consider discussing schedule balance"
                })

        # Development opportunities
        if not staff.is_supervisor and len(staff_shifts) > 10:
            recommendations.append({
                "type": "DEVELOPMENT",
                "priority": "LOW",
                "message": "Consider leadership training opportunities"
            })

        return recommendations

    # ===== OPTIMIZED METHODS =====
    # These methods use pre-computed data structures for O(1) lookups

    @staticmethod
    def _generate_summary_optimized(shifts, assignments, departments, assignments_by_shift, shift_map):
        """Optimized summary generation using pre-computed data"""
        total_shifts = len(shifts)
        total_staff = len(set(a.employee_id for a in assignments))
        departments_count = len(departments)

        # Calculate coverage using pre-grouped assignments
        fully_covered = sum(1 for shift in shifts
                          if len(assignments_by_shift.get(shift.id, [])) >= shift.min_staff)
        coverage_rate = (fully_covered / total_shifts * 100) if total_shifts else 0

        # Calculate totals
        total_hours = len(assignments) * 8
        estimated_cost = total_hours * 25
        average_utilization = round((total_hours / (total_staff * 40)) * 100, 1) if total_staff > 0 else 0

        # Generate insights efficiently
        insights = []
        if total_shifts > 0:
            day_shifts = [s for s in shifts if s.shift_type == "DAY"]
            night_shifts = [s for s in shifts if s.shift_type == "NIGHT"]

            if day_shifts and night_shifts:
                day_covered = sum(1 for s in day_shifts
                                if len(assignments_by_shift.get(s.id, [])) >= s.min_staff)
                night_covered = sum(1 for s in night_shifts
                                  if len(assignments_by_shift.get(s.id, [])) >= s.min_staff)

                day_coverage = (day_covered / len(day_shifts) * 100)
                night_coverage = (night_covered / len(night_shifts) * 100)
                insights.append(f"Day shifts have {day_coverage:.1f}% coverage vs {night_coverage:.1f}% for nights")

        # Identify issues
        critical_issues = []
        if coverage_rate < 90:
            critical_issues.append(f"Low overall coverage rate: {coverage_rate:.1f}%")

        return {
            "total_shifts": total_shifts,
            "total_staff": total_staff,
            "departments_count": departments_count,
            "overall_coverage_rate": round(coverage_rate, 1),
            "total_scheduled_hours": total_hours,
            "estimated_cost": estimated_cost,
            "average_utilization": average_utilization,
            "quality_score": min(100, coverage_rate + 10),
            "critical_issues": critical_issues,
            "key_insights": insights
        }

    @staticmethod
    def _analyze_departments_optimized(departments, shifts_by_dept, assignments_by_shift, staff_map, dept_map):
        """Optimized department analysis using pre-grouped data"""
        dept_analysis = []

        for dept in departments:
            dept_shifts = shifts_by_dept.get(dept.id, [])
            dept_assignments = []
            for shift in dept_shifts:
                dept_assignments.extend(assignments_by_shift.get(shift.id, []))

            # Coverage by shift type
            shifts_by_type = {}
            for shift in dept_shifts:
                if shift.shift_type not in shifts_by_type:
                    shifts_by_type[shift.shift_type] = []
                shifts_by_type[shift.shift_type].append(shift)

            coverage_by_type = {}
            for shift_type, type_shifts in shifts_by_type.items():
                covered = sum(1 for s in type_shifts
                            if len(assignments_by_shift.get(s.id, [])) >= s.min_staff)
                coverage_by_type[shift_type] = {
                    "total": len(type_shifts),
                    "covered": covered,
                    "rate": round((covered / len(type_shifts)) * 100, 1) if type_shifts else 100
                }

            # Staff metrics
            assigned_staff_ids = set(a.employee_id for a in dept_assignments)
            dept_staff = [staff_map[emp_id] for emp_id in assigned_staff_ids if emp_id in staff_map]

            avg_shifts = len(dept_assignments) / len(dept_staff) if dept_staff else 0
            utilization = round((len(dept_assignments) * 8) / (len(dept_staff) * 40) * 100, 1) if dept_staff else 0

            dept_analysis.append({
                "department_id": dept.id,
                "name": dept.name,
                "shifts": {
                    "total": len(dept_shifts),
                    "fully_covered": sum(1 for s in dept_shifts
                                       if len(assignments_by_shift.get(s.id, [])) >= s.min_staff),
                    "coverage_rate": round(
                        (sum(1 for s in dept_shifts
                            if len(assignments_by_shift.get(s.id, [])) >= s.min_staff) /
                         len(dept_shifts)) * 100, 1) if dept_shifts else 100,
                    "by_type": coverage_by_type
                },
                "staff": {
                    "assigned_count": len(dept_staff),
                    "average_shifts_per_staff": round(avg_shifts, 1),
                    "utilization_rate": utilization,
                    "supervisor_coverage": 100,  # Placeholder
                    "skill_gaps": []  # Placeholder
                },
                "metrics": {
                    "total_hours": len(dept_assignments) * 8,
                    "estimated_cost": len(dept_assignments) * 8 * 25,
                    "avg_score": 85.5,  # Placeholder
                    "overtime_shifts": 0,  # Placeholder
                    "consecutive_day_violations": 0  # Placeholder
                }
            })

        return dept_analysis

    @staticmethod
    def _analyze_staff_optimized(staff_list, assignments_by_staff, shift_map, dept_map):
        """Optimized staff analysis using pre-grouped assignments"""
        staff_analysis = []

        for staff in staff_list:
            staff_assignments = assignments_by_staff.get(staff.employee_id, [])
            staff_shifts = [shift_map[assignment.shift_id] for assignment in staff_assignments
                          if assignment.shift_id in shift_map]

            # Shift type distribution
            shifts_by_type = {}
            for shift in staff_shifts:
                shifts_by_type[shift.shift_type] = shifts_by_type.get(shift.shift_type, 0) + 1

            total_hours = len(staff_assignments) * 8
            overtime_hours = max(0, total_hours - 40)

            # Skills analysis
            proficient_skills = [f"Skill_{skill_id}_L{level}"
                               for skill_id, level in staff.skills.items()]

            # Get skill IDs from assigned shifts
            assigned_skill_ids = set()
            for shift in staff_shifts:
                assigned_skill_ids.update(shift.required_skill_ids)

            utilized_skills = [f"Skill_{skill_id}" for skill_id in staff.skills
                             if skill_id in assigned_skill_ids]
            underutilized_skills = [f"Skill_{skill_id}" for skill_id in staff.skills
                                  if skill_id not in assigned_skill_ids]

            skill_match_rate = (len(utilized_skills) / len(staff.skills) * 100) if staff.skills else 0

            # Preferences (placeholder)
            preferences = {
                "preferred_shifts": ["DAY"],
                "preferred_percentage": 40,
                "actual_percentage": (shifts_by_type.get("DAY", 0) / len(staff_shifts) * 100) if staff_shifts else 0,
                "satisfaction_score": 100
            }

            # Get department info
            dept_id = staff_shifts[0].department_id if staff_shifts else staff.org_id

            # Generate recommendations
            recommendations = EnhancedAnalysisService._generate_staff_recommendations(
                staff, staff_shifts, total_hours, underutilized_skills, overtime_hours
            )

            staff_analysis.append({
                "employee_id": staff.employee_id,
                "full_name": staff.name,
                "role": staff.role,
                "department": {
                    "id": dept_id,
                    "name": dept_map.get(dept_id, {}).name if dept_id in dept_map else f"Department {dept_id}"
                },
                "assignments": {
                    "total_shifts": len(staff_shifts),
                    "total_hours": total_hours,
                    "by_type": shifts_by_type,
                    "consecutive_days": 0,
                    "weekends_worked": 0,
                    "overtime_hours": overtime_hours
                },
                "skills": {
                    "proficient": proficient_skills,
                    "utilized": utilized_skills,
                    "underutilized": underutilized_skills,
                    "skill_match_rate": round(skill_match_rate, 1)
                },
                "preferences": preferences,
                "performance": {
                    "avg_assignment_score": 78.5,
                    "supervisor_assignments": 0,
                    "critical_shifts": 0,
                    "recommendations": recommendations
                }
            })

        return staff_analysis

    @staticmethod
    def _detail_shifts_optimized(shifts, assignments_by_shift, dept_map, staff_map):
        """Optimized shift details using pre-grouped assignments"""
        detailed_shifts = []

        for shift in shifts:
            shift_assignments = assignments_by_shift.get(shift.id, [])
            assigned_staff = []

            for assignment in shift_assignments:
                staff = staff_map.get(assignment.employee_id)
                if staff:
                    assigned_staff.append({
                        "employee_id": staff.employee_id,
                        "full_name": staff.name,
                        "role": staff.role,
                        "is_supervisor": False,
                        "assigned_hours": 8,
                        "match_score": 85,
                        "skills_matched": []
                    })

            coverage_status = "ADEQUATE"
            if len(assigned_staff) < shift.min_staff:
                coverage_status = "UNDERSTAFFED"
            elif len(assigned_staff) > shift.max_staff:
                coverage_status = "OVERSTAFFED"

            detailed_shifts.append({
                "shift_id": shift.id,
                "date": shift.shift_date.isoformat(),
                "type": shift.shift_type,
                "department": {
                    "id": shift.department_id,
                    "name": dept_map.get(shift.department_id, {}).name if shift.department_id in dept_map else f"Dept {shift.department_id}"
                },
                "requirements": {
                    "min_staff": shift.min_staff,
                    "max_staff": shift.max_staff,
                    "requires_supervisor": False,
                    "required_skills": [],
                    "priority": shift.priority,
                    "hours": shift.hours
                },
                "assignments": assigned_staff,
                "coverage": {
                    "assigned_count": len(assigned_staff),
                    "meets_minimum": len(assigned_staff) >= shift.min_staff,
                    "coverage_status": coverage_status,
                    "skill_coverage": {}
                },
                "metrics": {
                    "total_score": 82.5,
                    "estimated_cost": len(assigned_staff) * 8 * 25,
                    "utilization_rate": round((len(assigned_staff) / shift.max_staff) * 100, 1) if shift.max_staff > 0 else 0
                }
            })

        return detailed_shifts

    @staticmethod
    def _calculate_analytics_optimized(shifts, assignments, staff_list, departments, assignments_by_shift):
        """Optimized analytics calculation using pre-grouped data"""
        # Fairness metrics
        shifts_per_staff = {}
        for assignment in assignments:
            shifts_per_staff[assignment.employee_id] = shifts_per_staff.get(assignment.employee_id, 0) + 1

        if len(shifts_per_staff) > 1:
            import statistics
            shift_variance = statistics.variance(list(shifts_per_staff.values()))
        else:
            shift_variance = 0

        # Cost analysis
        total_hours = len(assignments) * 8
        estimated_cost = total_hours * 25
        overtime_cost = sum(max(0, shifts_per_staff.get(emp, 0) * 8 - 40) * 37.5
                          for emp in shifts_per_staff)  # Time and a half for overtime

        return {
            "fairness_metrics": {
                "shift_distribution_variance": round(shift_variance, 2),
                "hour_distribution_variance": round(shift_variance * 64, 2),  # 8 hours per shift
                "weekend_distribution_score": 78.5  # Placeholder
            },
            "skill_analysis": {
                "overall_coverage": 89.2,  # Placeholder
                "critical_gaps": [],
                "surplus_skills": []
            },
            "cost_analysis": {
                "total_estimated_cost": estimated_cost,
                "cost_per_shift": round(estimated_cost / len(shifts), 2) if shifts else 0,
                "cost_per_hour": 25,
                "overtime_cost": overtime_cost,
                "optimization_potential": round(estimated_cost * 0.05, 2)
            },
            "quality_metrics": {
                "preference_satisfaction": 76.5,  # Placeholder
                "skill_utilization": 82.3,  # Placeholder
                "supervisor_coverage": 100,  # Placeholder
                "continuity_score": 85.7  # Placeholder
            },
            "trends": {
                "coverage_trend": "STABLE",
                "utilization_trend": "INCREASING",
                "issue_areas": []
            }
        }

    @staticmethod
    def _generate_recommendations_optimized(shifts, assignments_by_shift, departments, shift_map):
        """Optimized recommendations using pre-grouped data"""
        recommendations = {
            "immediate_actions": [],
            "skill_development": [],
            "optimization_opportunities": []
        }

        # Check for understaffed shifts
        understaffed_by_dept = {}
        for shift in shifts:
            if len(assignments_by_shift.get(shift.id, [])) < shift.min_staff:
                understaffed_by_dept[shift.department_id] = understaffed_by_dept.get(shift.department_id, 0) + 1

        for dept_id, count in understaffed_by_dept.items():
            if count > 0:
                recommendations["immediate_actions"].append({
                    "priority": "HIGH",
                    "category": "STAFFING",
                    "description": f"Department {dept_id} has {count} understaffed shifts",
                    "impact": "Improve coverage and service quality"
                })

        # Overtime recommendations
        shifts_per_staff = {}
        for assignments in assignments_by_shift.values():
            for assignment in assignments:
                shifts_per_staff[assignment.employee_id] = shifts_per_staff.get(assignment.employee_id, 0) + 1

        for emp_id, shifts_count in shifts_per_staff.items():
            hours = shifts_count * 8
            if hours > 45:  # More than 5 hours overtime
                recommendations["immediate_actions"].append({
                    "priority": "MEDIUM",
                    "category": "WORKLOAD",
                    "description": f"Staff {emp_id} has {hours - 40} overtime hours",
                    "impact": "Prevent burnout and reduce overtime costs"
                })

        # Optimization opportunities
        recommendations["optimization_opportunities"].append({
            "area": "Shift Distribution",
            "potential_savings": "$1000/month",
            "implementation": "Balance workload across staff members"
        })

        return recommendations