from typing import Dict
from datetime import date
from math import fabs
import json
import os
from pathlib import Path

class ScoringEngine:
    """
    Provide heuristics and scoring used both by greedy & cpsat.
    Weights are configurable via JSON file.
    """
    
    def __init__(self):
        """Initialize with configurable weights"""
        self.weights = self._load_weights()
    
    def _load_weights(self) -> Dict:
        """Load scoring weights from config file with fallback to defaults"""
        config_path = Path(__file__).parent.parent.parent / "config" / "scoring_weights.json"
        
        # Default weights (fallback)
        defaults = {
            "preferred_shift_bonus": 10.0,
            "skill_level_multiplier": 5.0,
            "skill_match_base": 20.0,
            "supervisor_bonus": 15.0,
            "department_familiarity": 5.0,
            "consecutive_day_penalty": -3.0,
            "overtime_penalty": -5.0,
            "weekend_penalty": -2.0
        }
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("weights", defaults)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load scoring weights from {config_path}: {e}")
        
        return defaults

    def score_staff_for_shift(self, staff, shift) -> float:
        """Score a staff member for a shift using configurable weights"""
        score = 0.0
        
        # Preferred shift bonus
        if shift.shift_type in staff.preferred_shifts:
            score += self.weights.get("preferred_shift_bonus", 10)
        
        # Skills matching
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
                score += lvl * self.weights.get("skill_level_multiplier", 5)
        
        # Supervisor bonus
        if shift.requires_supervisor and staff.is_supervisor:
            score += self.weights.get("supervisor_bonus", 20)
        
        # Priority boost
        score += shift.priority * 2
        
        # Utilization bias (prefer less utilized)
        util = staff.estimate_weekly_utilization()
        if util < 0.5:
            score += 5
        elif util > 0.9:
            score += self.weights.get("overtime_penalty", -10)
        
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
