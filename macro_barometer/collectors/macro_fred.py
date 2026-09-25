"""FRED collector. A missing API key is an explicit non-fatal condition."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping

import pandas as pd

from storage import Cache


@dataclass
class FredReport:
    name: str = "fred"
    stored: int = 0
    warnings: list[str] = field(default_factory=list)


def collect_fred_data(cache: Cache, series_map: Mapping[str, str], api_key: str | None, lookback_days: int = 400) -> FredReport:
    report = FredReport()
    if not api_key:
        report.warnings.append("FRED_API_KEY is not configured; using cached FRED data if present.")
        return report

    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
    except Exception as exc:
        report.warnings.append(f"Failed to initialize FRED client: {exc}")
        return report

    start = date.today() - timedelta(days=lookback_days)
    for metric, series_id in series_map.items():
        try:
            values = fred.get_series(series_id, observation_start=start).dropna()
            if values.empty:
                report.warnings.append(f"FRED series '{series_id}' ({metric}) returned no observations.")
                continue
            
            # Convert percentage to basis points for the dashboard chart
            if metric == "high_yield_spread":
                values = values * 100
                
            report.stored += cache.upsert_observations(metric, values.rename("value").to_frame(), f"fred:{series_id}")
        except Exception as exc:
            report.warnings.append(f"FRED series '{series_id}' ({metric}) failed: {exc}")

    return report