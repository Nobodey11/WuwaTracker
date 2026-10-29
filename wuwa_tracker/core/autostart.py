"""Start the tracker with Windows (per user, no admin rights): a value under
HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run, the same place Discord or Steam use.

It starts with --tray, so the app sits in the system tray until the game is started.
"""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "WuWaPullTracker"
ROOT = Path(__file__).resolve().parents[2]


def launch_command(extra: str = "--tray") -> str:
    """The command that starts this installation: the .exe when frozen, else pythonw + launcher.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {extra}'.strip()
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe") if exe.name.lower() == "python.exe" else exe
    if not pyw.exists():
        pyw = exe
    return f'"{pyw}" "{ROOT / "launcher.py"}" {extra}'.strip()


def steam_launch_option() -> str:
    """For Steam → Wuthering Waves → Properties → Launch options: start the tracker, then the game."""
    return f'cmd /c start "" {launch_command("--tray")} & %command%'


class _WinReg:
    def get(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                return winreg.QueryValueEx(k, VALUE)[0]
        except OSError:
            return None

    def set(self, cmd):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, cmd)

    def delete(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, VALUE)
        except OSError:
            pass


def _reg(reg):
    return reg or _WinReg()


def supported() -> bool:
    return sys.platform.startswith("win")


def is_enabled(reg=None) -> bool:
    if reg is None and not supported():
        return False
    return bool(_reg(reg).get())


def enable(reg=None, command: str | None = None) -> str:
    cmd = command or launch_command()
    _reg(reg).set(cmd)
    return cmd


def disable(reg=None) -> None:
    _reg(reg).delete()


def refresh(reg=None) -> None:
    """If enabled but pointing to an old location (moved folder / new .exe), rewrite it."""
    r = _reg(reg)
    cur = r.get()
    if cur and cur != launch_command():
        r.set(launch_command())
