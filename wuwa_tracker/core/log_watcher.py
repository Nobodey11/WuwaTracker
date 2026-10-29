"""Watch the game log for the Convene history being opened (for automatic imports).

The log is append-only while the game runs and the XOR scramble works per byte, so only the bytes added since the
last poll need decoding. Every NEW occurrence of a history link counts (also when it is the same link as before:
reopening the history in the same game session can reuse it). If the file shrinks (a new game session starts a fresh
log), it is read from the start again.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import game_import as gi

TAIL_OVERLAP = 4096     # re-read a bit before the old end, so a link split over two polls is still found
URL_RE_B = re.compile(gi.URL_RE.pattern.encode())


def links_with_end(data: bytes, base: int = 0) -> list[tuple[int, str]]:
    """(absolute end offset, url) of every link in the data, decoded (new game versions) or plain."""
    out = {}
    for blob in (gi.decode_client_log(data), data):
        for m in URL_RE_B.finditer(blob):
            out[base + m.end()] = m.group().decode("ascii", errors="ignore")
    return sorted(out.items())


class LogWatcher:
    def __init__(self, files: list[Path]):
        self.files = [Path(f) for f in files]
        self.pos: dict[Path, int] = {}          # bytes read so far
        self.seen: dict[Path, int] = {}         # end offset of the last link already handled
        self.last_url: str | None = None
        self.primed = False
        self.events = 0                          # history openings seen since priming

    def prime(self) -> None:
        """Remember what is already in the logs, so only links written from now on trigger an import."""
        for f in self.files:
            try:
                size = f.stat().st_size
            except OSError:
                continue
            found = self._scan(f, 0, size)
            if found:
                self.last_url = found[-1][1]
            self.pos[f] = self.seen[f] = size
        self.primed = True

    def _scan(self, f: Path, start: int, end: int) -> list[tuple[int, str]]:
        try:
            with open(f, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start)
        except OSError:
            return []
        return links_with_end(data, start)

    def poll(self) -> str | None:
        """Returns the history link if the history was opened (again) since the last poll, else None."""
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
            if size < old:          # log replaced / new session
                old = 0
                self.seen[f] = 0
            if size == old:
                continue
            hits = [(end, url) for end, url in self._scan(f, max(0, old - TAIL_OVERLAP), size)
                    if end > self.seen.get(f, 0)]
            self.pos[f] = size
            if hits:
                self.seen[f] = hits[-1][0]
                found = hits[-1][1]
        if found:
            self.last_url = found
            self.events += 1
        return found
