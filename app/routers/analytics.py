# app/routers/analytics.py
"""
Focused Analytics API Router

Provides 8 specialized endpoints for operational intelligence:
1. Safety Analysis - "Is the hospital/lab operationally safe today?"
2. Alert System - "What are the critical issues I need to address?"
3. Burnout Risk - "Is anyone at risk of burnout?"
4. Shift Risks - "Which shifts or departments are most at risk?"
5. Resilience - "Is the current schedule sustainable?"
6. Dependencies - "Are we relying too heavily on key staff?"
7. Fairness - "Is workload distributed fairly?"
8. Recommendations - "What would improve the situation most?"
"""
from fastapi import APIRouter, Depends, Security, Query
from fastapi.security import HTTPBearer
from sqlmodel import Session
from datetime import date, timedelta

from app.db.session import get_session
from app.core.security import get_current_user
from app.utils.organization_lookup import get_org_by_slug

# Import all schemas
from app.schemas_analytics import (
    SafetyAnalysis,
    AlertSystem,
    BurnoutRiskAnalysis,
    ShiftRiskAnalysis,
    DependencyAnalysis,
    FairnessAnalysis,
    RecommendationAnalysis,
)

# Import all services
from app.services.analytics import (
    SafetyAnalyticsService,
    AlertService,
    BurnoutAnalyticsService,
    ShiftRiskAnalyticsService,
    DependencyAnalyticsService,
    FairnessAnalyticsService,
    RecommendationAnalyticsService,
)

router = APIRouter(prefix="/{org_slug}/analytics", tags=["Analytics"])
security = HTTPBearer()


# ============================================================
# 1. SAFETY ANALYSIS
# ============================================================

@router.get("/safety", response_model=SafetyAnalysis, dependencies=[Security(security)])
def get_safety_analysis(
    org_slug: str,
    start_date: str = Query(None, description="ISO date, defaults to today"),
    end_date: str = Query(None, description="ISO date, defaults to today + 7 days"),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Operational Safety Analysis**
    
    Answers: "Is the hospital/lab operationally safe today?"
    
    Returns comprehensive safety assessment including:
    - Overall safety score (0-100)
    - Safety status (SAFE/CAUTION/CRITICAL)
    - Coverage rates (overall, supervisor, skills)
    - Critical staffing gaps
    
    **FIXED Features:**
    - ✅ Actual supervisor coverage calculation (no longer placeholder)
    - ✅ Actual skill coverage per shift (no longer placeholder)
    - ✅ Safety status thresholds (SAFE >= 90, CAUTION 70-89, CRITICAL < 70)
    """
    org = get_org_by_slug(org_slug, session)
    
    # Parse dates
    start = date.fromisoformat(start_date) if start_date else date.today()
    end = date.fromisoformat(end_date) if end_date else date.today() + timedelta(days=7)
    
    return SafetyAnalyticsService.analyze_safety(session, org.id, start, end)


# ============================================================
# 2. ALERT SYSTEM
# ============================================================

@router.get("/alerts", response_model=AlertSystem, dependencies=[Security(security)])
def get_alerts(
    org_slug: str,
    severity: str = Query(None, description="Filter by CRITICAL, WARNING, INFO"),
    category: str = Query(None, description="Filter by STAFFING, WORKLOAD, SKILLS, SUPERVISOR, SAFETY"),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Critical Issues Alert System**
    
    Answers: "What are the critical issues I need to address?"
    
    Aggregates all critical issues into actionable alerts:
    - Understaffed shifts
    - Missing supervisors
    - Skill coverage gaps
    - Workload/burnout risks
    
    Each alert includes:
    - Severity classification
    - Affected entities
    - Recommended actions
    """
    org = get_org_by_slug(org_slug, session)
    
    return AlertService.get_alerts(session, org.id, severity, category)


# ============================================================
# 3. BURNOUT RISK ANALYSIS
# ============================================================

@router.get("/burnout-risk", response_model=BurnoutRiskAnalysis, dependencies=[Security(security)])
def get_burnout_risk(
    org_slug: str,
    period_days: int = Query(30, description="Analysis period in days", ge=7, le=90),
    risk_level: str = Query(None, description="Filter by HIGH, MEDIUM, LOW"),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Burnout Risk Analysis**
    
    Answers: "Is anyone at risk of burnout?"
    
    Provides comprehensive burnout risk assessment:
    - Individual risk scores (0-100)
    - Risk level classification (HIGH/MEDIUM/LOW)
    - Contributing factors (overtime, consecutive days, night shifts, weekends)
    - Personalized recommendations
    
    **NEW Features:**
    - ✅ Consecutive days tracking (no longer placeholder)
    - ✅ Burnout risk scoring algorithm
    - ✅ Multi-factor analysis
    """
    org = get_org_by_slug(org_slug, session)
    
    analysis = BurnoutAnalyticsService.analyze_burnout_risk(session, org.id, period_days)
    
    # Apply risk level filter if specified
    if risk_level:
        analysis.staff_risks = [
            s for s in analysis.staff_risks 
            if s.risk_level == risk_level.upper()
        ]
        # Recalculate summary
        analysis.summary = BurnoutAnalyticsService._calculate_summary(analysis.staff_risks)
    
    return analysis


# ============================================================
# 4. SHIFT RISK ANALYSIS
# ============================================================

@router.get("/shift-risks", dependencies=[Security(security)])
def get_shift_risks(
    org_slug: str,
    start_date: str = Query(..., description="ISO date (required)"),
    end_date: str = Query(..., description="ISO date (required)"),
    min_risk_score: int = Query(None, description="Filter shifts with risk >= threshold", ge=0, le=100),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Shift and Department Risk Analysis**
    
    Answers: "Which shifts or departments are most at risk?"
    
    Provides comprehensive risk assessment including:
    - Individual shift risk scores
    - Risk factor identification
    - Department-level risk aggregation
    - Coverage status analysis
    """
    org = get_org_by_slug(org_slug, session)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    
    analysis = ShiftRiskAnalyticsService.analyze_shift_risks(session, org.id, start, end)
    
    # Apply risk score filter if specified
    if min_risk_score is not None:
        analysis.shift_risks = [s for s in analysis.shift_risks if s.risk_score >= min_risk_score]
    
    return analysis


# ============================================================
# 5. DEPENDENCY ANALYSIS
# ============================================================

@router.get("/dependencies", dependencies=[Security(security)])
def get_dependencies(
    org_slug: str,
    period_days: int = Query(30, description="Analysis period in days", ge=7, le=90),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Key Staff Dependency Analysis**
    
    Answers: "Are we relying too heavily on a small group of people?"
    
    Identifies:
    - Key staff members and their dependency scores
    - Bus factor (minimum people who could leave before crisis)
    - Skill concentration risks
    - Single points of failure
    """
    org = get_org_by_slug(org_slug, session)
    
    return DependencyAnalyticsService.analyze_dependencies(session, org.id, period_days)


# ============================================================
# 6. FAIRNESS METRICS
# ============================================================

@router.get("/fairness", dependencies=[Security(security)])
def get_fairness(
    org_slug: str,
    period: str = Query("30d", description="Analysis period (7d, 30d, 90d)"),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Workload Distribution Fairness Analysis**
    
    Answers: "Is workload distributed fairly?"
    
    Analyzes:
    - Gini coefficient for shift distribution
    - Weekend and night shift equity
    - Individual staff workload deviations
    - Overall fairness score
    """
    org = get_org_by_slug(org_slug, session)
    
    return FairnessAnalyticsService.analyze_fairness(session, org.id, period)


# ============================================================
# 7. RECOMMENDATIONS
# ============================================================

@router.get("/recommendations", dependencies=[Security(security)])
def get_recommendations(
    org_slug: str,
    priority: str = Query(None, description="Filter by HIGH, MEDIUM, LOW"),
    category: str = Query(None, description="Filter by STAFFING, SKILLS, WORKLOAD, etc."),
    session: Session = Depends(get_session),
    current: dict = Depends(get_current_user)
):
    """
    **Actionable Improvement Recommendations**
    
    Answers: "What would improve the situation most?"
    
    Provides:
    - Prioritized recommendations with impact estimates
    - Scenario analysis (hire staff vs. change rules vs. cross-train)
    - ROI calculations
    - Effort assessments
    """
    org = get_org_by_slug(org_slug, session)
    
    analysis = RecommendationAnalyticsService.generate_recommendations(session, org.id)
    
    # Apply filters
    if priority:
        analysis.recommendations = [
            r for r in analysis.recommendations 
            if r.priority == priority.upper()
        ]
    
    if category:
        analysis.recommendations = [
            r for r in analysis.recommendations 
            if r.category == category.upper()
        ]
    
    return analysis
