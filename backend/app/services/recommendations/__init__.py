"""
Recommendations service package.
"""
from app.services.recommendations.base import RecommendationService
from app.services.recommendations.rule_based import RuleBasedRecommendationService

__all__ = ["RecommendationService", "RuleBasedRecommendationService"]
