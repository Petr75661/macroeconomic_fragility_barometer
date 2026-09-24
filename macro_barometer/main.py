"""CLI entry point and optional interval runner for Project Barometer."""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv

from collectors.eia_data import collect_eia_data
from collectors.macro_fred import collect_fred_data
from collectors.market_data import collect_market_data
from collectors.news_collector import collect_news
from engine.index_calculator import PILLAR_METRICS, calculate_index
from engine.ollama_client import assess_news
from storage import Cache

ROOT = Path(__file__).resolve().parent


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    with (ROOT / "config.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def cache_for(config: dict) -> Cache:
    return Cache(ROOT / config["database_path"])


def save_current_snapshot(cache: Cache, config: dict) -> None:
    """Persist today's score after a data run; repeated same-day runs update the point."""
    metric_names = {metric for metrics in PILLAR_METRICS.values() for metric in metrics}
    series = {metric: cache.series(metric, 430) for metric in metric_names}
    geo = cache.geo_history(1)
    geo_score = None if geo.empty else float(geo.iloc[0].score)
    cache.save_fragility_snapshot(calculate_index(series, geo_score, config["weights"]))


def seed_demo(cache: Cache, days: int = 300) -> None:
    """Offline deterministic data used by tests, demos, and first-run UI exploration."""
    rng = np.random.default_rng(42)
    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    bases = {"brent": 78, "wti": 74, "crack_spread": 24, "spr_inventory": 380, "distillate_inventory": 120,
             "high_yield_spread": 380, "treasury_10y": 4.2, "yield_curve": .2, "real_yield_10y": 1.9,
             "financial_stress": -.5, "concentration_ratio": 1.0, "semi_staples_ratio": 5.0, "vix": 17,
             "dollar": 104, "bdc_relative": .82}
    for metric, base in bases.items():
        drift = np.linspace(0, rng.normal(0, abs(base) * .08), days)
        values = base + drift + rng.normal(0, max(abs(base) * .025, .02), days)
        cache.upsert_observations(metric, pd.DataFrame({"value": values}, index=index), "demo")
    cache.save_geo({"hormuz_shipping_threat": 2, "refinery_strike_damage": 2, "peace_deescalation_signals": 3,
                    "summary": "Demo data: no live geopolitical assessment has been run.", "score": 35.0}, "demo")
    # Seed a single, clearly labelled present-day snapshot; scheduled/live runs build the trend over time.
    save_current_snapshot(cache, load_config())


def refresh_all(config: dict, include_geo: bool = True) -> list[object]:
    cache = cache_for(config)
    reports = [
        collect_market_data(cache, config["tickers"], config.get("lookback_days", 400)),
        collect_fred_data(cache, config["fred_series"], os.getenv("FRED_API_KEY"), config.get("lookback_days", 400)),
        collect_eia_data(cache, config.get("eia", {}), os.getenv("EIA_API_KEY")),
    ]
    if include_geo:
        news = collect_news(config.get("rss_feeds", []))
        reports.append(news)
        result, status = assess_news(news.headlines, config["ollama"]["host"], config["ollama"]["model"], config["ollama"].get("timeout_seconds", 60))
        cache.save_geo(result, status)
    save_current_snapshot(cache, config)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Project Barometer local data runner")
    parser.add_argument("--refresh", action="store_true", help="Fetch market, macro, EIA and news data once.")
    parser.add_argument("--seed-demo", action="store_true", help="Write deterministic local demo series.")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="Repeat refresh on this interval.")
    args = parser.parse_args()
    config = load_config()
    cache = cache_for(config)
    if args.seed_demo:
        seed_demo(cache)
        print("Demo data written.")
    if args.refresh or args.watch:
        while True:
            reports = refresh_all(config)
            for report in reports:
                print(f"{report.name}: stored={getattr(report, 'stored', 0)}")
                for warning in getattr(report, "warnings", []):
                    print(f"  warning: {warning}")
            if not args.watch:
                break
            time.sleep(max(args.watch, 60))
    if not (args.seed_demo or args.refresh or args.watch):
        parser.print_help()


if __name__ == "__main__":
    main()
