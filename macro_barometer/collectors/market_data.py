"""Yahoo Finance market collector and derived market-stress measurements."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping

import pandas as pd

from storage import Cache


@dataclass
class CollectionReport:
    name: str
    stored: int = 0
    warnings: list[str] = field(default_factory=list)


def collect_market_data(cache: Cache, tickers: Mapping[str, str], lookback_days: int = 400) -> CollectionReport:
    report = CollectionReport("market")
    try:
        import yfinance as yf
        raw = yf.download(
            list(tickers.values()), start=date.today() - timedelta(days=lookback_days),
            auto_adjust=True, progress=False, group_by="column", threads=True,
        )
    except Exception as exc:  # Network failures must leave cached data usable.
        report.warnings.append(f"Yahoo Finance unavailable: {exc}")
        return report
    if raw.empty:
        report.warnings.append("Yahoo Finance returned no rows.")
        return report
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=list(tickers.values())[0])
    prices: dict[str, pd.Series] = {}
    for name, ticker in tickers.items():
        if ticker in close:
            series = close[ticker].dropna().rename("value")
            if not series.empty:
                report.stored += cache.upsert_observations(name, series.to_frame(), "yfinance")
                prices[name] = series
    def save_ratio(metric: str, numerator: str, denominator: str) -> None:
        if numerator in prices and denominator in prices:
            ratio = (prices[numerator] / prices[denominator]).dropna().rename("value")
            report.stored += cache.upsert_observations(metric, ratio.to_frame(), "derived:yfinance")
    if "heating_oil" in prices and "wti" in prices:
        crack = (prices["heating_oil"] * 42 - prices["wti"]).dropna().rename("value")
        report.stored += cache.upsert_observations("crack_spread", crack.to_frame(), "derived:yfinance")
    save_ratio("concentration_ratio", "spy", "rsp")
    save_ratio("semi_staples_ratio", "soxx", "xlp")
    save_ratio("bdc_relative", "bizd", "spy")
    if not prices:
        report.warnings.append("No configured ticker produced a usable close price.")
    return report
