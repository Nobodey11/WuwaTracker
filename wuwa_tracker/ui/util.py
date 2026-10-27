"""Small helpers shared by the tabs."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path(path) -> None:
    """Open a folder or file with the system's default program."""
    path = str(Path(path))
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


def pct(v: float | None, digits: int = 1) -> str:
    if v is None:
        return "–"
    if 0 < v < 0.0005:
        return "<0.1 %"
    if v > 0.9995 and v < 1:
        return ">99.9 %"
    return f"{v * 100:.{digits}f} %"
