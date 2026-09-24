import pandas as pd

from collectors.news_collector import collect_news
from main import seed_demo
from storage import Cache


def test_demo_populates_cache(tmp_path):
    cache = Cache(tmp_path / "barometer.db")
    seed_demo(cache, days=40)
    assert len(cache.series("brent")) == 40
    assert not cache.geo_history().empty
    assert len(cache.fragility_history()) == 1


def test_news_collector_accepts_empty_source_list():
    report = collect_news([])
    assert report.headlines == []
