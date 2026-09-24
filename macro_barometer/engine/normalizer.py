"""Rolling, direction-aware 0-100 transformations."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_fragility_score(series: pd.Series, window: int = 252, high_is_fragile: bool = True) -> pd.Series:
    """Winsorized rolling min-max score; returns NaN until enough history exists."""
    values = pd.to_numeric(series, errors="coerce").astype(float)
    lower = values.rolling(window, min_periods=min(20, window)).quantile(0.05)
    upper = values.rolling(window, min_periods=min(20, window)).quantile(0.95)
    clipped = values.clip(lower=lower, upper=upper)
    span = (upper - lower).replace(0, np.nan)
    score = ((clipped - lower) / span * 100).clip(0, 100)
    return score if high_is_fragile else (100 - score)


def latest_score(series: pd.Series, window: int = 252, high_is_fragile: bool = True) -> float | None:
    score = rolling_fragility_score(series, window, high_is_fragile).dropna()
    return None if score.empty else float(score.iloc[-1])
