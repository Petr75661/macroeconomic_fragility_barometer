"""RSS ingestion, deliberately limited to headlines and summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class NewsReport:
    name: str = "news"
    headlines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def collect_news(feeds: Iterable[str], max_items_per_feed: int = 12) -> NewsReport:
    report = NewsReport()
    try:
        import feedparser
    except ImportError:
        report.warnings.append("feedparser is not installed.")
        return report
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(getattr(parsed, "bozo_exception", "invalid feed"))
            for entry in parsed.entries[:max_items_per_feed]:
                title = str(entry.get("title", "")).strip()
                summary = str(entry.get("summary", "")).strip()
                if title:
                    report.headlines.append(f"{title}. {summary[:280]}")
        except Exception as exc:
            report.warnings.append(f"RSS feed failed ({url}): {exc}")
    return report
