"""EIA weekly distillate and SPR inventory collector."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd
import requests

from storage import Cache


@dataclass
class EiaReport:
    name: str = "eia"
    stored: int = 0
    warnings: list[str] = field(default_factory=list)


def collect_eia_data(cache: Cache, settings: Mapping[str, str], api_key: str | None) -> EiaReport:
    report = EiaReport()
    if not api_key:
        report.warnings.append("EIA_API_KEY is not configured; using cached EIA data if present.")
        return report

    series_targets = {
        "distillate_inventory": settings.get("distillate_series", "PET.WDISTUS1.W"),
        "spr_inventory": settings.get("spr_series", "PET.WCSSTUS1.W"),
    }

    for metric, series_id in series_targets.items():
        url = f"https://api.eia.gov/v2/seriesid/{series_id}"
        try:
            response = requests.get(url, params={"api_key": api_key, "out": "json"}, timeout=30)
            response.raise_for_status()
            data = response.json().get("response", {}).get("data", [])
            frame = pd.DataFrame(data)
            if frame.empty or not {"period", "value"}.issubset(frame):
                raise ValueError("unexpected EIA response shape")
            frame["period"] = pd.to_datetime(frame["period"])
            frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
            
            # EIA reports SPR in thousand barrels; dividing by 1,000 matches 
            # the "million barrels" unit displayed in the dashboard
            if metric == "spr_inventory":
                frame["value"] = frame["value"] / 1000.0

            stored_count = cache.upsert_observations(
                metric, frame.set_index("period")[["value"]].dropna(), f"eia:{series_id}"
            )
            report.stored += stored_count
        except Exception as exc:
            report.warnings.append(f"EIA {metric} ({series_id}) failed: {exc}")

    return report