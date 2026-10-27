"""Automatic, dated copies of pulls.db (made before every import) and restore."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

KEEP = 20


@dataclass
class Backup:
    path: Path
    when: datetime
    reason: str
    pulls: int

    @property
    def label(self) -> str:
        return f"{self.when:%Y-%m-%d %H:%M:%S} · {self.reason} · {self.pulls:,} pulls"


def backup_dir(db_path: Path) -> Path:
    d = Path(db_path).parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_backup(con: sqlite3.Connection, db_path: Path, reason: str = "manual", keep: int = KEEP) -> Path:
    """Consistent copy through SQLite's backup API (safe while the app has the DB open)."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in reason)[:30] or "backup"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = backup_dir(db_path) / f"pulls-{stamp}-{safe}.db"
    out = sqlite3.connect(dest)
    try:
        con.backup(out)
    finally:
        out.close()
    prune(db_path, keep)
    return dest


def list_backups(db_path: Path) -> list[Backup]:
    out = []
    for p in sorted(backup_dir(db_path).glob("pulls-*.db"), reverse=True):
        parts = p.stem.split("-", 4)          # pulls, date, time, micro, reason
        try:
            when = datetime.strptime(parts[1] + parts[2], "%Y%m%d%H%M%S")
        except (IndexError, ValueError):
            when = datetime.fromtimestamp(p.stat().st_mtime)
        reason = parts[4] if len(parts) > 4 else ""
        try:
            c = sqlite3.connect(p)
            n = c.execute("SELECT COUNT(*) FROM pulls").fetchone()[0]
            c.close()
        except sqlite3.Error:
            n = 0
        out.append(Backup(p, when, reason, n))
    return out


def prune(db_path: Path, keep: int = KEEP) -> None:
    files = sorted(backup_dir(db_path).glob("pulls-*.db"), reverse=True)
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def restore(con: sqlite3.Connection, backup_path: Path) -> None:
    """Overwrite the open database with the backup's contents (in place, the connection stays valid)."""
    src = sqlite3.connect(backup_path)
    try:
        src.backup(con)
    finally:
        src.close()
