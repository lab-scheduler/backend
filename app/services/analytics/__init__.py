# app/services/analytics/__init__.py
"""
Focused analytics services for operational intelligence.
Each service provides specific insights for decision-making.
"""

from .safety_service import SafetyAnalyticsService
from .alert_service import AlertService
from .burnout_service import BurnoutAnalyticsService
from .shift_risk_service import ShiftRiskAnalyticsService
from .dependency_service import DependencyAnalyticsService
from .fairness_service import FairnessAnalyticsService
from .recommendation_service import RecommendationAnalyticsService

__all__ = [
    "SafetyAnalyticsService",
    "AlertService",
    "BurnoutAnalyticsService",
    "ShiftRiskAnalyticsService",
    "DependencyAnalyticsService",
    "FairnessAnalyticsService",
    "RecommendationAnalyticsService",
]
