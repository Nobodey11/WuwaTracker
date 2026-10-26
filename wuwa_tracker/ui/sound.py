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
        self._thread = None

    def preload(self):
        """Generate the WAV files in a background thread (takes about a second the first time)."""
        if self._thread is None and self.ok is None:
            import threading
            from ..core.sounds import ensure_sounds

            def work():
                try:
                    self.paths = ensure_sounds(self.folder)
                except Exception:
                    self.paths = {}
            self._thread = threading.Thread(target=work, daemon=True)
            self._thread.start()

    def _load(self):
        if self.ok is not None:
            return self.ok
        try:
            if self._thread is None:
                self.preload()
            self._thread.join(timeout=5)
            if not self.paths:
                raise RuntimeError("sounds not generated")
            if HAVE_QT_AUDIO:
                for name, p in self.paths.items():
                    e = QSoundEffect()
                    e.setSource(QUrl.fromLocalFile(str(p)))
                    self.effects[name] = e
            self.ok = True
        except Exception:
            self.ok = False
        return self.ok

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
