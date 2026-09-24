import pandas as pd

from engine.index_calculator import calculate_index, classify
from engine.normalizer import rolling_fragility_score


def test_score_is_bounded_and_direction_aware():
    index = pd.bdate_range("2025-01-01", periods=40)
    rising = pd.Series(range(40), index=index)
    high = rolling_fragility_score(rising, window=30).dropna().iloc[-1]
    low = rolling_fragility_score(rising, window=30, high_is_fragile=False).dropna().iloc[-1]
    assert 0 <= high <= 100
    assert high > low


def test_index_rebalances_when_only_one_pillar_available():
    dates = pd.bdate_range("2025-01-01", periods=45)
    result = calculate_index({"brent": pd.Series(range(45), index=dates)}, None, {"energy": .3, "credit": .25, "market": .2, "geopolitics": .25})
    assert result.score is not None
    assert result.data_quality == 25
    assert result.zone == classify(result.score)
