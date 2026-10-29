"""1.1: game detection, start with Windows, log watcher per history opening, retries, session controller."""
import os
from pathlib import Path

import pytest

from wuwa_tracker.core import autostart, game_import as gi
from wuwa_tracker.core.game_watch import GameWatcher, parse_names, running_processes
from wuwa_tracker.core.log_watcher import LogWatcher
from tests.test_game_import import URL, encode_client_log


def test_game_watcher_start_stop_with_grace():
    procs = {"explorer.exe"}
    clock = [0.0]
    w = GameWatcher(["Client-Win64-Shipping.exe"], lister=lambda: procs, clock=lambda: clock[0])
    assert w.poll() is None
    procs.add("client-win64-shipping.exe")
    assert w.poll() == "started" and w.running
    assert w.poll() is None
    procs.discard("client-win64-shipping.exe")
    assert w.poll() is None                 # one miss is tolerated (restart / crash reporter)
    clock[0] = 1800
    assert w.poll() == "stopped" and w.last.minutes == 30
    assert parse_names("a.exe, b.exe\nc.exe,") == ["a.exe", "b.exe", "c.exe"]
    assert isinstance(running_processes(), set)


class FakeReg:
    def __init__(self):
        self.v = None

    def get(self):
        return self.v

    def set(self, c):
        self.v = c

    def delete(self):
        self.v = None


def test_autostart_registry_roundtrip():
    r = FakeReg()
    assert not autostart.is_enabled(r)
    cmd = autostart.enable(r)
    assert autostart.is_enabled(r) and "--tray" in cmd and "launcher.py" in cmd
    r.v = '"C:/old/pythonw.exe" "C:/old/launcher.py" --tray'
    autostart.refresh(r)
    assert r.v == autostart.launch_command()
    autostart.disable(r)
    assert not autostart.is_enabled(r)
    assert autostart.steam_launch_option().endswith("%command%")


def test_reopening_history_with_same_link_counts(tmp_path):
    f = tmp_path / "Client.log"
    f.write_bytes(encode_client_log(f"start {URL}\n".encode()))
    w = LogWatcher([f])
    assert w.poll() is None                                  # prime: existing link ignored
    with open(f, "ab") as fh:
        fh.write(encode_client_log(f"open again {URL}\n".encode()))
    assert w.poll() == URL                                   # same link, new opening -> import
    with open(f, "ab") as fh:
        fh.write(encode_client_log(b"some other log line\n" * 50))
    assert w.poll() is None                                  # overlap re-read doesn't re-trigger
    with open(f, "ab") as fh:
        fh.write(encode_client_log(f"{URL}\n".encode()))
    assert w.poll() == URL and w.events == 2


def test_import_worker_retries(monkeypatch):
    pytest.importorskip("PySide6")
    from wuwa_tracker.ui.background import GameImportWorker
    calls = []

    def flaky(url, off, existing, log):
        calls.append(1)
        if len(calls) < 3:
            raise gi.ImportError_("link not active yet")
        return gi.GameImportResult([], "1", 8, [])
    monkeypatch.setattr(gi, "import_from_game", flaky)
    w = GameImportWorker(None, URL, 8, [], retries=2, retry_delay=0)
    out = []
    w.done.connect(lambda r, e: out.append((r, e)))
    w.run()
    assert len(calls) == 3 and out and out[0][1] == ""
    calls.clear()
    w2 = GameImportWorker(None, URL, 8, [], retries=0, retry_delay=0)
    w2.done.connect(lambda r, e: out.append((r, e)))
    w2.run()
    assert "not active" in out[-1][1]


def test_session_controller(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication, QMainWindow
    app = QApplication.instance() or QApplication([])
    from wuwa_tracker.core.storage import Storage
    from wuwa_tracker.ui.state import AppState
    from wuwa_tracker.ui import session as sess

    class FakeWorker:
        def __init__(self, *a, **k):
            from PySide6.QtCore import QObject, Signal
            class S(QObject):
                link_found = Signal(str)
                status = Signal(str)
            self._s = S(); self.link_found = self._s.link_found; self.status = self._s.status
            self.running = False
        def start(self): self.running = True
        def stop(self): self.running = False
        def wait(self, ms): return True
    monkeypatch.setattr(sess, "LogWatchWorker", FakeWorker)

    class Win(QMainWindow):
        def __init__(self):
            super().__init__()
            self.notes, self.imports, self.shown, self.quit = [], [], 0, False
        def notify(self, t, x): self.notes.append(t)
        def import_game(self, **k): self.imports.append(k)
        def show_window(self): self.shown += 1
        def quit_app(self): self.quit = True

    st = Storage(tmp_path / "p.db")
    for k, v in {"auto_import": True, "game_detect": True, "overlay": False, "open_on_game": True,
                 "prydwen_enabled": False}.items():
        st.set_setting(k, v)
    state = AppState(st)
    win = Win()
    c = sess.SessionController(win, state)
    procs = set()
    c.game.lister = lambda: procs
    c.apply()
    assert c.watcher is None and not c.in_game            # waiting for the game: no log watching
    procs.add("client-win64-shipping.exe")
    c.poll()
    assert c.in_game and c.watcher is not None and win.shown == 1 and "Wuthering Waves started" in win.notes
    c.watcher.link_found.emit(URL); c.watcher.link_found.emit(URL)
    c._fire_import()                                       # debounced: two openings -> one import
    assert len(win.imports) == 1 and win.imports[0]["auto"] and win.imports[0]["retries"] == 2
    c.imported(10, ["Lynae"])
    procs.clear()
    c.poll(); c.poll()
    assert not c.in_game and c.watcher is None
    assert "Session summary" in win.notes
    c.shutdown()
