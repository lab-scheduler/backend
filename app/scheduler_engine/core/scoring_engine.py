from typing import Dict
from datetime import date
from math import fabs

class ScoringEngine:
    """
    Provide heuristics and scoring used both by greedy & cpsat.
    Derived from optimization.py's metrics.
    """

    def score_staff_for_shift(self, staff, shift) -> float:
        score = 0.0
        # preferred shift
        if shift.shift_type in staff.preferred_shifts:
            score += 10
        # skills
        for skill_id in shift.required_skill_ids:
            if staff.has_skill(skill_id):
                lvl = staff.skills.get(skill_id, 0)
                # Convert skill level string to numeric value
                if isinstance(lvl, str):
                    skill_scores = {
                        "BASIC": 1,
                        "INTERMEDIATE": 2,
                        "ADVANCED": 3,
                        "EXPERT": 4
                    }
                    lvl = skill_scores.get(lvl.upper(), 0)
                score += lvl * 5
        # supervisor
        if shift.requires_supervisor and staff.is_supervisor:
            score += 20
        # priority boost
        score += shift.priority * 2
        # utilization bias (prefer less utilized)
        util = staff.estimate_weekly_utilization()
        if util < 0.5:
            score += 5
        elif util > 0.9:
            score -= 10
        return score

    def analyze_schedule(self, engine) -> Dict:
        # reuse the analyzer logic in optimization.py but simplified for API
        total_shifts = len(engine.shifts)
        covered = sum(1 for s in engine.shifts if len(s.assigned_staff_ids) >= s.min_staff)
        coverage_rate = (covered / total_shifts * 100) if total_shifts else 100
        return {
            "total_shifts": total_shifts,
            "fully_covered": covered,
            "coverage_rate": coverage_rate
        }
