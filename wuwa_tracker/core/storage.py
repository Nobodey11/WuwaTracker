"""SQLite storage + importers for wuwatracker JSON exports."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Pull

SCHEMA = """
CREATE TABLE IF NOT EXISTS pulls (
    player_id   TEXT    NOT NULL,
    pool_type   INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    quality     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    time        TEXT    NOT NULL,   -- ISO-8601 UTC
    grp         INTEGER NOT NULL,   -- order inside a 10-pull (wuwatracker 'group')
    PRIMARY KEY (player_id, pool_type, time, grp, resource_id)
);
CREATE INDEX IF NOT EXISTS idx_pool ON pulls(player_id, pool_type, time, grp);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def default_db_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "WuwaTracker"
    p.mkdir(parents=True, exist_ok=True)
    return p / "pulls.db"


def parse_time(s: str) -> datetime:
    """Accepts '2026-10-26T10:52:48+00:00' (export) or '2026-10-26 18:52:48' (game API, server-local)."""
    s = s.strip()
    if "T" not in s:
        s = s.replace(" ", "T")
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class Storage:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.con = sqlite3.connect(self.path)
        self.con.executescript(SCHEMA)

    # ---------- settings ----------
    def get_setting(self, key: str, default=None):
        row = self.con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value) -> None:
        self.con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))
        self.con.commit()

    # ---------- pulls ----------
    def add_pulls(self, pulls: list[Pull]) -> int:
        """Insert pulls, ignoring duplicates. Returns number of new rows."""
        before = self.count()
        self.con.executemany(
            "INSERT OR IGNORE INTO pulls VALUES (?,?,?,?,?,?,?)",
            [(p.player_id, p.pool_type, p.resource_id, p.quality, p.name, p.time.isoformat(), p.group) for p in pulls],
        )
        self.con.commit()
        return self.count() - before

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM pulls").fetchone()[0]

    def players(self) -> list[str]:
        return [r[0] for r in self.con.execute("SELECT DISTINCT player_id FROM pulls ORDER BY player_id")]

    def load(self, player_id: str | None = None) -> list[Pull]:
        q = "SELECT player_id, pool_type, resource_id, quality, name, time, grp FROM pulls"
        args: tuple = ()
        if player_id:
            q += " WHERE player_id=?"
            args = (player_id,)
        q += " ORDER BY pool_type, time, grp"
        return [
            Pull(pool_type=r[1], resource_id=r[2], quality=r[3], name=r[4],
                 time=datetime.fromisoformat(r[5]), group=r[6], player_id=r[0])
            for r in self.con.execute(q, args)
        ]

    def clear(self, player_id: str | None = None) -> None:
        if player_id:
            self.con.execute("DELETE FROM pulls WHERE player_id=?", (player_id,))
        else:
            self.con.execute("DELETE FROM pulls")
        self.con.commit()

    # ---------- import / export ----------
    def import_wuwatracker_json(self, path: str | Path) -> tuple[int, int, str]:
        """Returns (new_rows, total_in_file, player_id)."""
        pulls, player = read_wuwatracker_json(path)
        return self.add_pulls(pulls), len(pulls), player

    def export_wuwatracker_json(self, path: str | Path, player_id: str) -> None:
        pulls = sorted(self.load(player_id), key=lambda p: (p.time, p.group), reverse=True)
        data = {
            "version": "0.0.2",
            "date": datetime.now(timezone.utc).isoformat(),
            "playerId": player_id,
            "pulls": [
                {"cardPoolType": p.pool_type, "resourceId": p.resource_id, "qualityLevel": p.quality,
                 "name": p.name, "time": p.time.isoformat(), "isSorted": True, "group": p.group}
                for p in pulls
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def export_csv(self, path: str | Path, player_id: str | None = None) -> None:
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["player_id", "pool_type", "resource_id", "quality", "name", "time_utc", "group"])
            for p in self.load(player_id):
                w.writerow([p.player_id, p.pool_type, p.resource_id, p.quality, p.name, p.time.isoformat(), p.group])


def read_wuwatracker_json(path: str | Path) -> tuple[list[Pull], str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    player = str(data.get("playerId", "") or "")
    pulls = [
        Pull(pool_type=int(r["cardPoolType"]), resource_id=int(r["resourceId"]), quality=int(r["qualityLevel"]),
             name=r["name"], time=parse_time(r["time"]), group=int(r.get("group", 0)), player_id=player)
        for r in data["pulls"]
    ]
    return pulls, player
