"""SQLite storage + importers for wuwatracker JSON exports."""
from __future__ import annotations

import json
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
CREATE TABLE IF NOT EXISTS income (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT    NOT NULL DEFAULT '',
    day       TEXT    NOT NULL,          -- YYYY-MM-DD
    astrite   INTEGER NOT NULL DEFAULT 0,
    tides     INTEGER NOT NULL DEFAULT 0,  -- Radiant Tides (character banner tickets)
    forging   INTEGER NOT NULL DEFAULT 0,  -- Forging Tides (weapon banner tickets)
    source    TEXT    NOT NULL DEFAULT '',
    note      TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_income ON income(player_id, day);
CREATE TABLE IF NOT EXISTS accounts (player_id TEXT PRIMARY KEY, nickname TEXT NOT NULL DEFAULT '');
"""


def default_db_path() -> Path:
    from .paths import data_dir
    return data_dir() / "pulls.db"


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

    # ---------- backups ----------
    def backup(self, reason: str = "manual") -> Path:
        from .backup import make_backup
        return make_backup(self.con, self.path, reason)

    def restore(self, backup_path) -> None:
        from .backup import restore
        restore(self.con, backup_path)
        self.con.executescript(SCHEMA)          # older backups may miss newer tables

    # ---------- accounts ----------
    def nicknames(self) -> dict[str, str]:
        return dict(self.con.execute("SELECT player_id, nickname FROM accounts"))

    def set_nickname(self, player_id: str, nickname: str) -> None:
        self.con.execute("INSERT OR REPLACE INTO accounts VALUES (?, ?)", (player_id, nickname.strip()))
        self.con.commit()

    # ---------- income (Astrite planner) ----------
    def add_income(self, day: str, astrite: int = 0, tides: int = 0, forging: int = 0, source: str = "",
                   note: str = "", player_id: str = "") -> int:
        cur = self.con.execute("INSERT INTO income (player_id, day, astrite, tides, forging, source, note) "
                               "VALUES (?,?,?,?,?,?,?)", (player_id, day, int(astrite), int(tides), int(forging),
                                                          source, note))
        self.con.commit()
        return cur.lastrowid

    def income(self, player_id: str | None = None) -> list[dict]:
        q = "SELECT id, player_id, day, astrite, tides, forging, source, note FROM income"
        args: tuple = ()
        if player_id is not None:
            q += " WHERE player_id IN (?, '')"
            args = (player_id,)
        cols = ("id", "player_id", "day", "astrite", "tides", "forging", "source", "note")
        return [dict(zip(cols, r)) for r in self.con.execute(q + " ORDER BY day, id", args)]

    def delete_income(self, row_id: int) -> None:
        self.con.execute("DELETE FROM income WHERE id=?", (row_id,))
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


    def export_xlsx(self, path: str | Path, player_id: str | None = None, gd=None) -> None:
        """Excel workbook: all pulls (with pity) + one summary sheet per banner. Needs openpyxl."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from .analysis import all_stats, pity_with_rows
        pulls = self.load(player_id)
        wb = Workbook()
        ws = wb.active
        ws.title = "Pulls"
        ws.append(["Player", "Banner type", "Rarity", "Name", "Time (UTC)", "Group", "5★ pity", "Resource id"])
        gold, purple = PatternFill("solid", fgColor="F5C518"), PatternFill("solid", fgColor="B48CFF")
        for p, pity in pity_with_rows(pulls):
            ws.append([p.player_id, p.pool_type, p.quality, p.name, p.time.replace(tzinfo=None), p.group, pity,
                       p.resource_id])
            if p.quality >= 4:
                ws.cell(ws.max_row, 3).fill = gold if p.quality == 5 else purple
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col, w in zip("ABCDEFGH", (12, 12, 8, 28, 20, 7, 9, 12)):
            ws.column_dimensions[col].width = w
        s = wb.create_sheet("Banners")
        s.append(["Banner", "Type", "Pulls", "Astrite", "5★ pity now", "4★ pity now", "5★", "4★", "Avg 5★ pity",
                  "50/50 won", "50/50 lost", "Guaranteed"])
        for st in all_stats(pulls, gd).values():
            s.append([st.name, st.pool_type, st.total_pulls, st.astrite, st.pity5, st.pity4, st.count5, st.count4,
                      round(st.avg_pity5, 2) if st.avg_pity5 else None, st.wins, st.losses,
                      "yes" if st.guaranteed else ("no" if st.has_5050 else "")])
        for c in s[1]:
            c.font = Font(bold=True)
        s.column_dimensions["A"].width = 28
        f = wb.create_sheet("5★ history")
        f.append(["Banner", "Name", "Pity", "Date (UTC)", "Result"])
        for st in all_stats(pulls, gd).values():
            for e in st.five_stars:
                f.append([st.name, e.name, e.pity, e.time.replace(tzinfo=None), e.result])
        for c in f[1]:
            c.font = Font(bold=True)
        f.column_dimensions["A"].width = 28
        f.column_dimensions["B"].width = 26
        f.column_dimensions["D"].width = 20
        wb.save(path)


def read_wuwatracker_json(path: str | Path) -> tuple[list[Pull], str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    player = str(data.get("playerId", "") or "")
    pulls = [
        Pull(pool_type=int(r["cardPoolType"]), resource_id=int(r["resourceId"]), quality=int(r["qualityLevel"]),
             name=r["name"], time=parse_time(r["time"]), group=int(r.get("group", 0)), player_id=player)
        for r in data["pulls"]
    ]
    return pulls, player
