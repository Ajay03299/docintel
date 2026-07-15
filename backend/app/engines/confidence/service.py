from app.engines.confidence.strategies import get_strategy
from app.schemas.confidence import ConfidenceReport, FieldScore


class ConfidenceService:
    """Aggregates per-field scores into a document-level report.
    Strategy and weights are injected — the engine knows nothing about invoices."""

    def __init__(self, strategy_name: str = "min_gated") -> None:
        self._strategy = get_strategy(strategy_name)

    def build_report(
        self,
        *,
        scores: list[FieldScore],
        weights: dict[str, float],
        critical: set[str],
    ) -> ConfidenceReport:
        overall = self._strategy.aggregate(scores, weights, critical)
        return ConfidenceReport(
            strategy=self._strategy.name,
            overall=round(max(0.0, min(1.0, overall)), 4),
            fields=scores,
            critical_fields=sorted(critical),
        )