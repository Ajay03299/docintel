import math
from abc import ABC, abstractmethod

from app.schemas.confidence import FieldScore


class AggregationStrategy(ABC):
    """Combines per-field confidences into one document-level score."""
    name: str

    @abstractmethod
    def aggregate(
        self, scores: list[FieldScore], weights: dict[str, float], critical: set[str]
    ) -> float: ...


class WeightedArithmeticMean(AggregationStrategy):
    """Forgiving: failures average out. Included for comparison — a missing
    total on an otherwise-perfect invoice still scores ~0.70 here, which is
    precisely why it is NOT our default."""
    name = "weighted_arithmetic"

    def aggregate(self, scores, weights, critical) -> float:
        den = sum(weights.get(s.field, 1.0) for s in scores)
        if den == 0:
            return 0.0
        num = sum(weights.get(s.field, 1.0) * s.confidence for s in scores)
        return num / den


class WeightedGeometricMean(AggregationStrategy):
    """Harsh: any near-zero field drags the product toward zero. Good at
    punishing failure, bad at distinguishing critical from trivial fields."""
    name = "weighted_geometric"
    _EPS = 1e-6

    def aggregate(self, scores, weights, critical) -> float:
        den = sum(weights.get(s.field, 1.0) for s in scores)
        if den == 0:
            return 0.0
        log_sum = sum(
            weights.get(s.field, 1.0) * math.log(max(s.confidence, self._EPS))
            for s in scores
        )
        return math.exp(log_sum / den)


class MinGatedWeightedMean(AggregationStrategy):
    """DEFAULT. Weighted mean overall, but gated by the weakest CRITICAL field:

        overall = min( weighted_arithmetic_mean(all), min(critical field scores) )

    A trivial field (discount) scoring 0 barely moves the score; a critical
    field (total) scoring 0 caps the document at 0. Fully explainable: the
    score is always attributable to a named field."""
    name = "min_gated"

    def __init__(self, base: AggregationStrategy | None = None) -> None:
        self._base = base or WeightedArithmeticMean()

    def aggregate(self, scores, weights, critical) -> float:
        base = self._base.aggregate(scores, weights, critical)
        critical_scores = [s.confidence for s in scores if s.field in critical]
        if not critical_scores:
            return base
        return min(base, min(critical_scores))


_REGISTRY: dict[str, AggregationStrategy] = {
    s.name: s for s in (WeightedArithmeticMean(), WeightedGeometricMean(), MinGatedWeightedMean())
}


def get_strategy(name: str) -> AggregationStrategy:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown confidence strategy {name!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]