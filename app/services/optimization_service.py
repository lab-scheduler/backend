# app/services/optimization_service.py
from app.core.optimization import DetailedAnalyzer

class OptimizationService:
    def __init__(self, session, state):
        self.session = session
        self.state = state

    def analyze(self):
        analyzer = DetailedAnalyzer(self.state, self.session)
        return analyzer.analyze()
