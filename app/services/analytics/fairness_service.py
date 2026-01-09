# app/services/analytics/fairness_service.py
"""
Fairness Analytics Service - Answers: "Is workload distributed fairly?"

Analyzes workload distribution equity across staff members.
"""
from datetime import date, timedelta
from typing import List, Dict
from collections import defaultdict
from sqlmodel import Session
import statistics

from app.scheduler_engine.adapters.db_adapter import DBAdapter
from app.schemas_analytics import (
    FairnessAnalysis,
    FairnessMetrics,
    StaffWorkload
)


class FairnessAnalyticsService:
    """Workload distribution fairness analysis service"""
    
    @staticmethod
    def analyze_fairness(session: Session, org_id: int, period: str = "30d") -> FairnessAnalysis:
        """
        Comprehensive fairness analysis.
        
        Answers: "Is workload distributed fairly?"
        """
        # Parse period
        period_days = int(period.replace("d", ""))
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
        
        # Calculate staff workloads
        staff_distribution = []
        shift_counts = []
        hour_counts = []
        
        for staff in staff_list:
            staff_assignments = assignments_by_staff.get(staff.employee_id, [])
            
            if not staff_assignments:
                continue
            
            # Count shifts
            total_shifts = len(staff_assignments)
            total_hours = total_shifts * 8  # Assuming 8 hours per shift
            
            # Count weekend and night shifts
            weekend_shifts = sum(
                1 for a in staff_assignments
                if a.shift_id in shift_map and shift_map[a.shift_id].shift_date.weekday() in [5, 6]
            )
            
            night_shifts = sum(
                1 for a in staff_assignments
                if a.shift_id in shift_map and shift_map[a.shift_id].shift_type == "NIGHT"
            )
            
            staff_distribution.append(StaffWorkload(
                employee_id=staff.employee_id,
                full_name=staff.name,
                total_shifts=total_shifts,
                total_hours=total_hours,
                weekend_shifts=weekend_shifts,
                night_shifts=night_shifts,
                fairness_deviation=0.0  # Will be calculated later
            ))
            
            shift_counts.append(total_shifts)
            hour_counts.append(total_hours)
        
        # Calculate fairness metrics
        metrics = FairnessAnalyticsService._calculate_metrics(
            shift_counts, hour_counts, staff_distribution, shift_map, assignments_by_staff
        )
        
        # Calculate deviations from average
        avg_shifts = statistics.mean(shift_counts) if shift_counts else 0
        for staff_workload in staff_distribution:
            staff_workload.fairness_deviation = round(
                ((staff_workload.total_shifts - avg_shifts) / avg_shifts * 100) if avg_shifts > 0 else 0,
                1
            )
        
        # Sort by deviation (most overworked first)
        staff_distribution.sort(key=lambda x: x.fairness_deviation, reverse=True)
        
        # Calculate overall fairness score
        fairness_score = FairnessAnalyticsService._calculate_fairness_score(metrics)
        
        return FairnessAnalysis(
            fairness_score=fairness_score,
            metrics=metrics,
            staff_distribution=staff_distribution,
            period=period
        )
    
    @staticmethod
    def _calculate_metrics(shift_counts: List[int], hour_counts: List[int],
                          staff_distribution: List, shift_map: Dict,
                          assignments_by_staff: Dict) -> FairnessMetrics:
        """Calculate fairness metrics"""
        
        # Shift distribution variance
        shift_variance = statistics.variance(shift_counts) if len(shift_counts) > 1 else 0.0
        
        # Hour distribution variance
        hour_variance = statistics.variance(hour_counts) if len(hour_counts) > 1 else 0.0
        
        # Gini coefficient for shift distribution
        gini = FairnessAnalyticsService._calculate_gini(shift_counts)
        
        # Weekend distribution score
        weekend_counts = [s.weekend_shifts for s in staff_distribution]
        weekend_score = FairnessAnalyticsService._calculate_distribution_score(weekend_counts)
        
        # Night shift distribution score
        night_counts = [s.night_shifts for s in staff_distribution]
        night_score = FairnessAnalyticsService._calculate_distribution_score(night_counts)
        
        return FairnessMetrics(
            shift_distribution_variance=round(shift_variance, 2),
            hour_distribution_variance=round(hour_variance, 2),
            gini_coefficient=round(gini, 3),
            weekend_distribution_score=round(weekend_score, 1),
            night_shift_distribution_score=round(night_score, 1)
        )
    
    @staticmethod
    def _calculate_gini(values: List[int]) -> float:
        """
        Calculate Gini coefficient (0 = perfect equality, 1 = perfect inequality).
        """
        if not values or len(values) < 2:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = 0
        
        for i, value in enumerate(sorted_values):
            cumsum += (i + 1) * value
        
        total = sum(sorted_values)
        if total == 0:
            return 0.0
        
        gini = (2 * cumsum) / (n * total) - (n + 1) / n
        return max(0.0, min(1.0, gini))
    
    @staticmethod
    def _calculate_distribution_score(counts: List[int]) -> float:
        """
        Calculate distribution score (0-100, higher is more fair).
        
        Based on coefficient of variation (lower CV = more fair).
        """
        if not counts or len(counts) < 2:
            return 100.0
        
        mean = statistics.mean(counts)
        if mean == 0:
            return 100.0
        
        stdev = statistics.stdev(counts)
        cv = stdev / mean  # Coefficient of variation
        
        # Convert to score (0 CV = 100, high CV = 0)
        # CV of 1.0 or higher = score of 0
        score = max(0, 100 - (cv * 100))
        
        return score
    
    @staticmethod
    def _calculate_fairness_score(metrics: FairnessMetrics) -> int:
        """
        Calculate overall fairness score (0-100).
        
        Based on:
        - Gini coefficient (lower is better): 40% weight
        - Weekend distribution: 30% weight
        - Night shift distribution: 30% weight
        """
        # Gini score (invert so lower Gini = higher score)
        gini_score = (1 - metrics.gini_coefficient) * 100
        
        # Weighted average
        score = (
            gini_score * 0.40 +
            metrics.weekend_distribution_score * 0.30 +
            metrics.night_shift_distribution_score * 0.30
        )
        
        return int(score)
