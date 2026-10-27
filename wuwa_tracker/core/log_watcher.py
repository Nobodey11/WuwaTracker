"""Watch the game log for a fresh Convene history link (for automatic imports).

The log is append-only while the game runs and the XOR scramble works per byte, so only the bytes added
since the last poll need decoding. If the file shrinks (new game session), it is read from the start again.
"""
from __future__ import annotations

from pathlib import Path

from . import game_import as gi

TAIL_OVERLAP = 4096     # re-read a bit before the old end, so a link split over two polls is still found


class LogWatcher:
    def __init__(self, files: list[Path]):
        self.files = [Path(f) for f in files]
        self.pos: dict[Path, int] = {}
        self.last_url: str | None = None
        self.primed = False

    def prime(self) -> None:
        """Remember the link that is already in the logs, so only NEW links trigger an import."""
        for f in self.files:
            try:
                size = f.stat().st_size
            except OSError:
                continue
            url = self._scan(f, 0, size)
            if url:
                self.last_url = url
            self.pos[f] = size
        self.primed = True

    def _scan(self, f: Path, start: int, end: int) -> str | None:
        try:
            with open(f, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start)
        except OSError:
            return None
        return gi.find_url_in_bytes(data)

    def poll(self) -> str | None:
        """Returns a history link that appeared since the last poll, else None."""
        if not self.primed:
            self.prime()
            return None
        found = None
        for f in self.files:
            try:
                size = f.stat().st_size
            except OSError:
                continue
            old = self.pos.get(f, 0)
            if size < old:          # log rotated / new session
                old = 0
            if size == old:
                continue
            url = self._scan(f, max(0, old - TAIL_OVERLAP), size)
            self.pos[f] = size
            if url and url != self.last_url:
                found = url
        if found:
            self.last_url = found
        return found
