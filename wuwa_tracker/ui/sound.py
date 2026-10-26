"""Plays the synthesised Convene sound effects (QtMultimedia, with a Windows-only fallback)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    if os.environ.get("WUWA_NO_AUDIO"):       # headless tests / no sound device
        raise ImportError
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
    HAVE_QT_AUDIO = True
except Exception:            # PySide6-Addons not installed
    HAVE_QT_AUDIO = False


class SoundPlayer:
    def __init__(self, folder: Path, enabled=lambda: True, volume=lambda: 0.7):
        self.folder = Path(folder)
        self.enabled = enabled
        self.volume = volume
        self.paths: dict[str, Path] = {}
        self.effects = {}
        self.ok = None

    def _load(self):
        if self.ok is not None:
            return self.ok
        try:
            from ..core.sounds import ensure_sounds
            self.paths = ensure_sounds(self.folder)
            if HAVE_QT_AUDIO:
                for name, p in self.paths.items():
                    e = QSoundEffect()
                    e.setSource(QUrl.fromLocalFile(str(p)))
                    self.effects[name] = e
            self.ok = True
        except Exception:
            self.ok = False
        return self.ok

    def preload(self):
        self._load()

    def play(self, name: str):
        if not self.enabled() or not self._load() or name not in self.paths:
            return
        if HAVE_QT_AUDIO:
            e = self.effects[name]
            e.setVolume(max(0.0, min(1.0, self.volume())))
            e.play()
        elif sys.platform.startswith("win") and not os.environ.get("WUWA_NO_AUDIO"):          # fallback: one sound at a time
            try:
                import winsound
                winsound.PlaySound(str(self.paths[name]), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:
                pass
