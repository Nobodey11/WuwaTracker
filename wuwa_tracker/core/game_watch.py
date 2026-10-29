"""Is Wuthering Waves running?  Lists running programs (no third-party packages) and turns that into
"game started" / "game stopped" events.

Only the list of process NAMES is read, the same information Task Manager shows. The game itself is never touched.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

# The game client; the launcher names are only used to say "launcher open" in the status chip.
GAME_PROCESSES = ["Client-Win64-Shipping.exe", "Wuthering Waves.exe"]
LAUNCHER_PROCESSES = ["launcher.exe", "KRLauncher.exe"]


def parse_names(text: str) -> list[str]:
    """'a.exe, b.exe' / one per line -> list (empty entries dropped)."""
    return [n.strip() for n in text.replace("\n", ",").split(",") if n.strip()]


def running_processes() -> set[str]:
    """Lower-case executable names of every running process."""
    if sys.platform.startswith("win"):
        return _windows_processes()
    out = set()
    for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if pid.isdigit():
            try:
                with open(f"/proc/{pid}/comm", encoding="utf-8", errors="replace") as f:
                    out.add(f.read().strip().lower())
            except OSError:
                pass
    return out


def _windows_processes() -> set[str]:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)          # TH32CS_SNAPPROCESS
    if snap in (None, wintypes.HANDLE(-1).value):
        return set()
    out = set()
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out.add(e.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return out


@dataclass
class Session:
    started: float
    ended: float | None = None
    imports: int = 0              # successful imports during the session
    new_pulls: int = 0
    five_stars: list[str] = field(default_factory=list)
    reminded: bool = False

    @property
    def minutes(self) -> float:
        return ((self.ended or time.time()) - self.started) / 60


class GameWatcher:
    """Call poll() every few seconds; returns "started", "stopped" or None."""

    def __init__(self, names: list[str] | None = None, lister=running_processes, clock=time.time,
                 stop_grace: int = 2):
        self.names = {n.lower() for n in (names or GAME_PROCESSES)}
        self.lister = lister
        self.clock = clock
        self.stop_grace = stop_grace        # polls in a row without the game before "stopped" (restart-proof)
        self.running = False
        self._misses = 0
        self.session: Session | None = None
        self.last: Session | None = None

    def is_running_now(self) -> bool:
        try:
            return bool(self.names & self.lister())
        except Exception:
            return False

    def poll(self) -> str | None:
        now_running = self.is_running_now()
        if now_running:
            self._misses = 0
            if not self.running:
                self.running = True
                self.session = Session(self.clock())
                return "started"
            return None
        if self.running:
            self._misses += 1
            if self._misses >= self.stop_grace:
                self.running = False
                self._misses = 0
                if self.session:
                    self.session.ended = self.clock()
                self.last, self.session = self.session, None
                return "stopped"
        return None
