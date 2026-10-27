"""Where the app keeps its files, plus a small lock so two PCs don't write the same synced database at once.

%APPDATA%/WuwaTracker/location.json  (always local) can point the data folder somewhere else, e.g. a OneDrive folder:
    {"data_dir": "C:/Users/me/OneDrive/WuwaTracker"}
Everything else (pulls.db, game data, Prydwen cache, backups, notes) lives in the data folder.
Small UI preferences that must be known before the window is built (theme, language) live in
%APPDATA%/WuwaTracker/ui.json, also always local.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import time
from pathlib import Path

LOCK_STALE_S = 6 * 3600     # a lock older than this (no heartbeat) is ignored


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "WuwaTracker"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def data_dir() -> Path:
    d = _read_json(app_dir() / "location.json").get("data_dir")
    if d:
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            pass          # folder unreachable (e.g. drive missing): fall back to the local folder
    return app_dir()


def set_data_dir(new: str | Path | None, move: bool = True) -> Path:
    """Point the app to another data folder. With move=True, files are copied over when the new folder has none."""
    old = data_dir()
    target = Path(new) if new else app_dir()
    target.mkdir(parents=True, exist_ok=True)
    if move and target.resolve() != old.resolve() and not (target / "pulls.db").exists():
        for name in ("pulls.db", "game_data.user.json", "game_data.remote.json"):
            if (old / name).exists():
                shutil.copy2(old / name, target / name)
        for sub in ("notes", "backups"):
            if (old / sub).is_dir() and not (target / sub).exists():
                shutil.copytree(old / sub, target / sub)
    loc = app_dir() / "location.json"
    if new:
        loc.write_text(json.dumps({"data_dir": str(target)}, indent=2), encoding="utf-8")
    elif loc.exists():
        loc.write_text("{}", encoding="utf-8")
    return target


def ui_prefs() -> dict:
    return _read_json(app_dir() / "ui.json")


def set_ui_pref(key: str, value) -> None:
    prefs = ui_prefs()
    prefs[key] = value
    (app_dir() / "ui.json").write_text(json.dumps(prefs, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- lock
def _me() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def acquire_lock(folder: Path) -> str | None:
    """Write a lock file. Returns a description of ANOTHER live holder (another PC/process), or None if we got it."""
    lock = Path(folder) / "pulls.db.lock"
    info = _read_json(lock) if lock.exists() else {}
    holder, beat = info.get("holder"), info.get("time", 0)
    if holder and holder != _me() and time.time() - beat < LOCK_STALE_S:
        host = holder.split(":")[0]
        if host != socket.gethostname() or _pid_alive(int(holder.split(":")[1] or 0)):
            return f"{host} (since {time.strftime('%Y-%m-%d %H:%M', time.localtime(beat))})"
    heartbeat(folder)
    return None


def heartbeat(folder: Path) -> None:
    try:
        (Path(folder) / "pulls.db.lock").write_text(json.dumps({"holder": _me(), "time": time.time()}),
                                                     encoding="utf-8")
    except OSError:
        pass


def release_lock(folder: Path) -> None:
    lock = Path(folder) / "pulls.db.lock"
    if lock.exists() and _read_json(lock).get("holder") == _me():
        try:
            lock.unlink()
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return True
