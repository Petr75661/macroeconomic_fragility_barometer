"""Four-pillar macro fragility score calculation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from engine.normalizer import latest_score


PILLAR_METRICS: dict[str, dict[str, bool]] = {
    "energy": {"brent": True, "wti": True, "crack_spread": True, "spr_inventory": False, "distillate_inventory": False},
    "credit": {"high_yield_spread": True, "treasury_10y": True, "yield_curve": False, "real_yield_10y": True, "financial_stress": True},
    "market": {"concentration_ratio": True, "semi_staples_ratio": True, "vix": True, "dollar": True, "bdc_relative": False},
}
ZONES = ((35, "Green"), (60, "Yellow"), (80, "Orange"), (100, "Red"))


@dataclass(frozen=True)
class IndexResult:
    score: float | None
    zone: str
    pillars: dict[str, float | None]
    components: dict[str, float | None]
    data_quality: int


def classify(score: float | None) -> str:
    if score is None:
        return "Unavailable"
    return next(label for upper, label in ZONES if score <= upper)


def calculate_index(series: Mapping[str, pd.Series], geo_score: float | None, weights: Mapping[str, float]) -> IndexResult:
    components: dict[str, float | None] = {}
    pillars: dict[str, float | None] = {}
    for pillar, metrics in PILLAR_METRICS.items():
        scores = []
        for metric, high_is_fragile in metrics.items():
            value = latest_score(series.get(metric, pd.Series(dtype=float)), high_is_fragile=high_is_fragile)
            components[metric] = value
            if value is not None:
                scores.append(value)
        pillars[pillar] = round(sum(scores) / len(scores), 1) if scores else None
    pillars["geopolitics"] = None if geo_score is None else round(float(geo_score), 1)
    available = {key: value for key, value in pillars.items() if value is not None}
    if not available:
        return IndexResult(None, "Unavailable", pillars, components, 0)
    total_weight = sum(float(weights.get(key, 0)) for key in available)
    score = sum(float(weights[key]) * value for key, value in available.items()) / total_weight
    quality = round(100 * len(available) / 4)
    return IndexResult(round(score, 1), classify(score), pillars, components, quality)
