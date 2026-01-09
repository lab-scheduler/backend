# app/services/analytics/burnout_service.py
"""
Burnout Risk Analytics Service - Answers: "Is anyone at risk of burnout?"

Provides comprehensive burnout risk assessment including:
- Consecutive days tracking (FIXED - no longer placeholder)
- Burnout risk scoring system (NEW)
- Overtime, night shifts, weekend tracking
- Personalized recommendations
"""
from datetime import date, timedelta
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    BurnoutRiskAnalysis,
    StaffBurnoutRisk,
    BurnoutFactors,
    BurnoutSummary
)


class BurnoutAnalyticsService:
    """Burnout risk analysis service"""
    
    @staticmethod
    def analyze_burnout_risk(session: Session, org_id: int, period_days: int = 30) -> BurnoutRiskAnalysis:
        """
        Comprehensive burnout risk analysis for all staff.
        
        Answers: "Is anyone at risk of burnout?"
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
        
        # Analyze each staff member
        staff_risks = []
        for staff in staff_list:
            staff_assignments = assignments_by_staff.get(staff.employee_id, [])
            
            if not staff_assignments:
                continue  # Skip staff with no assignments
            
            staff_shifts = [shift_map[a.shift_id] for a in staff_assignments if a.shift_id in shift_map]
            
            # Calculate burnout factors
            factors = BurnoutAnalyticsService._calculate_burnout_factors(
                staff, staff_shifts, staff_assignments, period_days
            )
            
            # Calculate risk score
            risk_score = BurnoutAnalyticsService._calculate_burnout_risk_score(factors)
            
            # Determine risk level
            risk_level = BurnoutAnalyticsService._get_risk_level(risk_score)
            
            # Generate recommendations
            recommendations = BurnoutAnalyticsService._generate_burnout_recommendations(
                staff, factors, risk_level
            )
            
            staff_risks.append(StaffBurnoutRisk(
                employee_id=staff.employee_id,
                full_name=staff.name,
                risk_score=risk_score,
                risk_level=risk_level,
                factors=factors,
                recommendations=recommendations
            ))
        
        # Sort by risk score (highest first)
        staff_risks.sort(key=lambda x: x.risk_score, reverse=True)
        
        # Calculate summary
        summary = BurnoutAnalyticsService._calculate_summary(staff_risks)
        
        return BurnoutRiskAnalysis(
            staff_risks=staff_risks,
            summary=summary,
            period_days=period_days
        )
    
    @staticmethod
    def _calculate_burnout_factors(staff, staff_shifts: List, staff_assignments: List, period_days: int) -> BurnoutFactors:
        """Calculate all factors contributing to burnout risk"""
        
        # Total hours
        total_hours = len(staff_assignments) * 8  # Assuming 8 hours per shift
        
        # Overtime hours (assuming 40 hours per week baseline)
        weeks = period_days / 7
        expected_hours = int(weeks * staff.max_hours_per_week)
        overtime_hours = max(0, total_hours - expected_hours)
        
        # Utilization rate
        utilization_rate = (total_hours / expected_hours * 100) if expected_hours > 0 else 0
        
        # FIXED: Calculate consecutive days (was placeholder at 0)
        consecutive_days = BurnoutAnalyticsService._calculate_consecutive_days(staff_shifts)
        
        # Night shift count
        night_shift_count = sum(1 for shift in staff_shifts if shift.shift_type == "NIGHT")
        
        # Weekend count
        weekend_count = sum(1 for shift in staff_shifts if shift.shift_date.weekday() in [5, 6])
        
        return BurnoutFactors(
            overtime_hours=overtime_hours,
            consecutive_days=consecutive_days,
            night_shift_count=night_shift_count,
            weekend_count=weekend_count,
            total_hours=total_hours,
            utilization_rate=round(utilization_rate, 1),
            max_hours_per_week=staff.max_hours_per_week
        )
    
    @staticmethod
    def _calculate_consecutive_days(staff_shifts: List) -> int:
        """
        FIXED: Calculate maximum consecutive days worked.
        
        Previously this was a placeholder returning 0.
        Now properly calculates the longest streak of consecutive days.
        """
        if not staff_shifts:
            return 0
        
        # Get unique dates and sort
        work_dates = sorted(set(shift.shift_date for shift in staff_shifts))
        
        if not work_dates:
            return 0
        
        max_consecutive = 1
        current_consecutive = 1
        
        for i in range(1, len(work_dates)):
            # Check if this date is consecutive to previous
            if work_dates[i] == work_dates[i-1] + timedelta(days=1):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        return max_consecutive
    
    @staticmethod
    def _calculate_burnout_risk_score(factors: BurnoutFactors) -> int:
        """
        NEW: Calculate burnout risk score (0-100) based on multiple factors.
        
        Scoring algorithm:
        - Overtime: +2 points per 10 hours over limit (max 20 points)
        - Consecutive days: +10 points per day over 5 (max 30 points)
        - Night shifts: +1 point per night shift (max 15 points)
        - Weekend frequency: +2 points per weekend (max 15 points)
        - Utilization: +20 points if > 90%, +10 if > 80%
        """
        score = 0
        
        # Overtime penalty
        if factors.overtime_hours > 0:
            score += min(int(factors.overtime_hours / 10) * 2, 20)
        
        # Consecutive days penalty
        if factors.consecutive_days > 5:
            score += min((factors.consecutive_days - 5) * 10, 30)
        
        # Night shift penalty
        score += min(factors.night_shift_count, 15)
        
        # Weekend penalty
        score += min(factors.weekend_count * 2, 15)
        
        # Utilization penalty
        if factors.utilization_rate > 90:
            score += 20
        elif factors.utilization_rate > 80:
            score += 10
        
        return min(100, score)
    
    @staticmethod
    def _get_risk_level(risk_score: int) -> str:
        """Determine risk level from score"""
        if risk_score >= 60:
            return "HIGH"
        elif risk_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"
    
    @staticmethod
    def _generate_burnout_recommendations(staff, factors: BurnoutFactors, risk_level: str) -> List[str]:
        """Generate personalized burnout prevention recommendations"""
        recommendations = []
        
        if risk_level == "HIGH":
            recommendations.append(f"⚠️ URGENT: {staff.name} is at high risk of burnout. Immediate action required.")
        
        if factors.overtime_hours > 10:
            recommendations.append(
                f"Reduce workload by {factors.overtime_hours} hours to prevent burnout"
            )
        
        if factors.consecutive_days > 5:
            recommendations.append(
                f"Schedule rest days - currently working {factors.consecutive_days} consecutive days"
            )
        
        if factors.night_shift_count > 8:
            recommendations.append(
                f"Reduce night shifts - currently assigned {factors.night_shift_count} night shifts"
            )
        
        if factors.weekend_count > 3:
            recommendations.append(
                f"Ensure weekend breaks - currently working {factors.weekend_count} weekends"
            )
        
        if factors.utilization_rate > 90:
            recommendations.append(
                f"Utilization at {factors.utilization_rate}% - redistribute workload to maintain sustainability"
            )
        
        if not recommendations:
            recommendations.append("Workload is within healthy limits - continue monitoring")
        
        return recommendations
    
    @staticmethod
    def _calculate_summary(staff_risks: List[StaffBurnoutRisk]) -> BurnoutSummary:
        """Calculate summary statistics"""
        high_risk = sum(1 for s in staff_risks if s.risk_level == "HIGH")
        medium_risk = sum(1 for s in staff_risks if s.risk_level == "MEDIUM")
        low_risk = sum(1 for s in staff_risks if s.risk_level == "LOW")
        
        avg_risk = sum(s.risk_score for s in staff_risks) / len(staff_risks) if staff_risks else 0
        
        return BurnoutSummary(
            high_risk=high_risk,
            medium_risk=medium_risk,
            low_risk=low_risk,
            total_staff=len(staff_risks),
            average_risk_score=round(avg_risk, 1)
        )
