"""Small SQLite cache shared by collectors and the dashboard."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


class Cache:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    metric TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    value REAL NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (metric, observed_at)
                );
                CREATE TABLE IF NOT EXISTS geo_assessments (
                    assessed_at TEXT PRIMARY KEY,
                    hormuz_shipping_threat INTEGER NOT NULL,
                    refinery_strike_damage INTEGER NOT NULL,
                    peace_deescalation_signals INTEGER NOT NULL,
                    score REAL NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ok'
                );
                CREATE TABLE IF NOT EXISTS fragility_history (
                    observed_at TEXT PRIMARY KEY,
                    score REAL NOT NULL,
                    zone TEXT NOT NULL,
                    energy_score REAL,
                    credit_score REAL,
                    market_score REAL,
                    geopolitics_score REAL,
                    data_quality INTEGER NOT NULL,
                    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def upsert_observations(self, metric: str, frame: pd.DataFrame, source: str) -> int:
        if frame.empty:
            return 0
        prepared = frame.copy()
        prepared.index = pd.to_datetime(prepared.index).tz_localize(None)
        prepared = prepared.rename_axis("observed_at").reset_index()
        value_column = "value" if "value" in prepared else prepared.columns[-1]
        rows = [
            (metric, pd.Timestamp(row.observed_at).strftime("%Y-%m-%d"), float(getattr(row, value_column)), source)
            for row in prepared.itertuples(index=False)
            if pd.notna(getattr(row, value_column))
        ]
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO observations(metric, observed_at, value, source)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(metric, observed_at) DO UPDATE SET
                     value=excluded.value, source=excluded.source, fetched_at=CURRENT_TIMESTAMP""",
                rows,
            )
        return len(rows)

    def series(self, metric: str, days: int | None = None) -> pd.Series:
        query = "SELECT observed_at, value FROM observations WHERE metric = ?"
        params: list[object] = [metric]
        if days:
            query += " AND observed_at >= date('now', ?)"
            params.append(f"-{days} days")
        query += " ORDER BY observed_at"
        with self._connect() as connection:
            frame = pd.read_sql_query(query, connection, params=params, parse_dates=["observed_at"])
        if frame.empty:
            return pd.Series(dtype=float, name=metric)
        return pd.Series(frame.value.to_numpy(), index=frame.observed_at, name=metric)

    def available_metrics(self) -> list[str]:
        with self._connect() as connection:
            return [row[0] for row in connection.execute("SELECT DISTINCT metric FROM observations ORDER BY metric")]

    def save_geo(self, result: dict[str, object], status: str = "ok") -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO geo_assessments
                   VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)""",
                (
                    result["hormuz_shipping_threat"], result["refinery_strike_damage"],
                    result["peace_deescalation_signals"], result["score"], result["summary"], status,
                ),
            )

    def geo_history(self, limit: int = 30) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM geo_assessments ORDER BY assessed_at DESC LIMIT ?", connection, params=[limit]
            )

    def save_fragility_snapshot(self, result: object) -> None:
        """Store one replaceable end-of-day composite score for long-term trend charts."""
        score = getattr(result, "score", None)
        if score is None:
            return
        pillars = getattr(result, "pillars")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO fragility_history
                   (observed_at, score, zone, energy_score, credit_score, market_score, geopolitics_score, data_quality)
                   VALUES (date('now'), ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(observed_at) DO UPDATE SET
                     score=excluded.score, zone=excluded.zone, energy_score=excluded.energy_score,
                     credit_score=excluded.credit_score, market_score=excluded.market_score,
                     geopolitics_score=excluded.geopolitics_score, data_quality=excluded.data_quality,
                     calculated_at=CURRENT_TIMESTAMP""",
                (
                    score, getattr(result, "zone"), pillars.get("energy"), pillars.get("credit"),
                    pillars.get("market"), pillars.get("geopolitics"), getattr(result, "data_quality"),
                ),
            )

    def fragility_history(self, days: int = 730) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                """SELECT observed_at, score, zone, energy_score, credit_score, market_score, geopolitics_score, data_quality
                   FROM fragility_history WHERE observed_at >= date('now', ?) ORDER BY observed_at""",
                connection, params=[f"-{days} days"], parse_dates=["observed_at"],
            )
