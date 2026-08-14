from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import ijson

from eft_scan.stats import PlayerMatch

_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    aid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_lc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_players_name_lc ON players(name_lc);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def json_to_sqlite(json_path: Path, sqlite_path: Path) -> int:
    tmp_path = sqlite_path.with_name(sqlite_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    connection = sqlite3.connect(tmp_path)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.executescript(_SCHEMA)
        inserted = 0
        batch: list[tuple[str, str, str]] = []
        with json_path.open("rb") as handle:
            for aid, name in ijson.kvitems(handle, ""):
                nickname = str(name)
                batch.append((str(aid), nickname, nickname.lower()))
                if len(batch) >= 10_000:
                    connection.executemany(
                        "INSERT OR REPLACE INTO players(aid, name, name_lc) VALUES (?, ?, ?)",
                        batch,
                    )
                    inserted += len(batch)
                    batch.clear()
            if batch:
                connection.executemany(
                    "INSERT OR REPLACE INTO players(aid, name, name_lc) VALUES (?, ?, ?)",
                    batch,
                )
                inserted += len(batch)
        connection.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('built_at', ?)",
            (str(time.time()),),
        )
        connection.commit()
    except Exception:
        connection.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    connection.close()
    tmp_path.replace(sqlite_path)
    return inserted


def search_sqlite(sqlite_path: Path, query: str, *, limit: int = 8) -> list[PlayerMatch]:
    raw = query.strip()
    if not raw or not sqlite_path.exists():
        return []
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        if raw.isdigit():
            row = connection.execute(
                "SELECT aid, name FROM players WHERE aid = ?",
                (raw,),
            ).fetchone()
            if row:
                return [PlayerMatch(row[0], row[1], exact=True)]
        key = raw.lower()
        exact = connection.execute(
            "SELECT aid, name FROM players WHERE name_lc = ? LIMIT ?",
            (key, limit),
        ).fetchall()
        if exact:
            return [PlayerMatch(aid, name, exact=True) for aid, name in exact]
        prefix = connection.execute(
            "SELECT aid, name FROM players WHERE name_lc LIKE ? ESCAPE '\\' "
            "ORDER BY name_lc LIMIT ?",
            (f"{_escape_like(key)}%", limit),
        ).fetchall()
        if prefix or len(key) < 4:
            return [PlayerMatch(aid, name, exact=False) for aid, name in prefix]
        contains = connection.execute(
            "SELECT aid, name FROM players WHERE name_lc LIKE ? ESCAPE '\\' LIMIT ?",
            (f"%{_escape_like(key)}%", limit),
        ).fetchall()
        return [PlayerMatch(aid, name, exact=False) for aid, name in contains]
    finally:
        connection.close()
