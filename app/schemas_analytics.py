# app/schemas_analytics.py
"""
Response schemas for focused analytics endpoints.
Each schema corresponds to a specific analytics endpoint.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import date, datetime


# ============================================================
# 1. SAFETY ANALYSIS SCHEMAS
# ============================================================

class CriticalGap(BaseModel):
    """A shift that doesn't meet minimum staffing requirements"""
    shift_id: int
    date: date
    shift_type: str
    department_name: str
    department_id: int
    required_staff: int
    assigned_staff: int
    gap: int
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    has_supervisor: bool
    missing_skills: List[str] = []


class SafetyAnalysis(BaseModel):
    """Overall operational safety assessment"""
    safety_score: int = Field(..., ge=0, le=100, description="Overall safety score 0-100")
    status: Literal["SAFE", "CAUTION", "CRITICAL"]
    coverage_rate: float = Field(..., description="Percentage of shifts meeting minimum requirements")
    minimum_requirements_met: bool
    supervisor_coverage_rate: float = Field(..., description="Percentage of supervisor-required shifts covered")
    skill_coverage_rate: float = Field(..., description="Percentage of shifts with all required skills")
    critical_gaps: List[CriticalGap]
    period: Dict[str, str] = Field(..., description="Analysis period start/end dates")


# ============================================================
# 2. ALERT SYSTEM SCHEMAS
# ============================================================

class Alert(BaseModel):
    """Individual alert/issue requiring attention"""
    id: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    category: Literal["STAFFING", "WORKLOAD", "SKILLS", "SUPERVISOR", "SAFETY"]
    title: str
    description: str
    affected_entities: List[str] = Field(..., description="shift IDs, staff IDs, or dept IDs")
    created_at: datetime
    actionable: bool
    recommended_action: Optional[str] = None


class AlertSummary(BaseModel):
    """Summary of alerts by severity"""
    critical: int
    warning: int
    info: int
    total: int


class AlertSystem(BaseModel):
    """Complete alert system response"""
    alerts: List[Alert]
    summary: AlertSummary


# ============================================================
# 3. BURNOUT RISK SCHEMAS
# ============================================================

class BurnoutFactors(BaseModel):
    """Factors contributing to burnout risk"""
    overtime_hours: int
    consecutive_days: int
    night_shift_count: int
    weekend_count: int
    total_hours: int
    utilization_rate: float
    max_hours_per_week: int


class StaffBurnoutRisk(BaseModel):
    """Burnout risk assessment for individual staff"""
    employee_id: str
    full_name: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    factors: BurnoutFactors
    recommendations: List[str]


class BurnoutSummary(BaseModel):
    """Summary of burnout risks across organization"""
    high_risk: int
    medium_risk: int
    low_risk: int
    total_staff: int
    average_risk_score: float


class BurnoutRiskAnalysis(BaseModel):
    """Complete burnout risk analysis"""
    staff_risks: List[StaffBurnoutRisk]
    summary: BurnoutSummary
    period_days: int


# ============================================================
# 4. SHIFT RISK SCHEMAS
# ============================================================

class ShiftRisk(BaseModel):
    """Risk assessment for individual shift"""
    shift_id: int
    date: date
    shift_type: str
    department_name: str
    department_id: int
    risk_score: int = Field(..., ge=0, le=100)
    risk_factors: List[str]
    coverage_status: Literal["UNDERSTAFFED", "ADEQUATE", "OVERSTAFFED"]
    assigned_count: int
    required_count: int
    has_supervisor: bool
    skill_gaps: List[str]


class DepartmentRisk(BaseModel):
    """Risk assessment for department"""
    department_id: int
    department_name: str
    risk_score: int = Field(..., ge=0, le=100)
    high_risk_shifts: int
    coverage_rate: float
    primary_concerns: List[str]


class ShiftRiskAnalysis(BaseModel):
    """Complete shift and department risk analysis"""
    shift_risks: List[ShiftRisk]
    department_risks: Dict[str, DepartmentRisk]
    period: Dict[str, str]


# ============================================================
# 5. RESILIENCE SCHEMAS
# ============================================================

class ResilienceMetrics(BaseModel):
    """Current resilience metrics"""
    average_utilization: float
    coverage_stability: float = Field(..., description="Variance in coverage over time")
    staff_turnover_risk: int = Field(..., ge=0, le=100)
    skill_redundancy: float = Field(..., description="Average number of people per critical skill")


class ResilienceProjections(BaseModel):
    """Projected future state"""
    projected_coverage_30d: float
    projected_utilization_30d: float
    early_warnings: List[str]


class ResilienceAnalysis(BaseModel):
    """System resilience and sustainability analysis"""
    resilience_score: int = Field(..., ge=0, le=100)
    sustainability_status: Literal["SUSTAINABLE", "AT_RISK", "UNSUSTAINABLE"]
    metrics: ResilienceMetrics
    projections: ResilienceProjections


# ============================================================
# 6. DEPENDENCY SCHEMAS
# ============================================================

class KeyStaffDependency(BaseModel):
    """Dependency analysis for key staff member"""
    employee_id: str
    full_name: str
    dependency_score: int = Field(..., ge=0, le=100, description="How critical this person is")
    shift_percentage: float = Field(..., description="Percentage of total shifts")
    unique_skills: List[str] = Field(..., description="Skills only this person has")
    critical_roles: List[str]
    impact_if_unavailable: str


class SkillDependency(BaseModel):
    """Dependency analysis for specific skill"""
    skill_id: int
    skill_name: str
    total_staff_with_skill: int
    expert_count: int
    single_point_of_failure: bool
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]


class DependencyAnalysis(BaseModel):
    """Complete dependency and key person analysis"""
    key_staff: List[KeyStaffDependency]
    bus_factor: int = Field(..., description="Minimum people who could leave before crisis")
    skill_dependencies: List[SkillDependency]
    concentration_risk: int = Field(..., ge=0, le=100, description="Overall concentration risk score")


# ============================================================
# 7. FAIRNESS SCHEMAS
# ============================================================

class FairnessMetrics(BaseModel):
    """Workload distribution fairness metrics"""
    shift_distribution_variance: float
    hour_distribution_variance: float
    gini_coefficient: float = Field(..., ge=0, le=1)
    weekend_distribution_score: float
    night_shift_distribution_score: float


class StaffWorkload(BaseModel):
    """Individual staff workload for fairness analysis"""
    employee_id: str
    full_name: str
    total_shifts: int
    total_hours: int
    weekend_shifts: int
    night_shifts: int
    fairness_deviation: float = Field(..., description="How far from average (positive = overworked)")


class FairnessAnalysis(BaseModel):
    """Complete fairness and equity analysis"""
    fairness_score: int = Field(..., ge=0, le=100)
    metrics: FairnessMetrics
    staff_distribution: List[StaffWorkload]
    period: str


# ============================================================
# 8. RECOMMENDATIONS SCHEMAS
# ============================================================

class Recommendation(BaseModel):
    """Individual recommendation"""
    id: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    category: Literal["STAFFING", "SKILLS", "WORKLOAD", "OPTIMIZATION", "POLICY"]
    title: str
    description: str
    impact: str
    effort: Literal["LOW", "MEDIUM", "HIGH"]
    estimated_improvement: Dict[str, float] = Field(
        ..., 
        description="Expected improvements, e.g., {'coverage': 5.0, 'burnout_reduction': 10.0}"
    )


class Scenario(BaseModel):
    """What-if scenario analysis"""
    name: str
    description: str
    actions: List[str]
    estimated_cost: Optional[str] = None
    expected_outcomes: Dict[str, str]
    roi_months: Optional[int] = None


class ScenarioAnalysis(BaseModel):
    """Comparison of different improvement scenarios"""
    scenarios: List[Scenario]


class RecommendationAnalysis(BaseModel):
    """Complete recommendations and scenario analysis"""
    recommendations: List[Recommendation]
    scenario_analysis: ScenarioAnalysis
