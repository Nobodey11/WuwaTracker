"""Game session controller: notices when Wuthering Waves starts and stops, runs the log watcher during the game,
imports (debounced, with retries) whenever you open Convene → History, reminds you to sync, shows the overlay,
and sums up the session when the game closes."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.game_watch import GAME_PROCESSES, GameWatcher, parse_names
from .background import LogWatchWorker

POLL_MS = 5_000            # how often the process list is checked
DEBOUNCE_MS = 3_000        # wait this long after the last history opening before importing
REMIND_AFTER_MIN = 20      # remind to sync after this many minutes of play without an import


class SessionController(QObject):
    status = Signal(str, str)          # chip text, tooltip
    game_started = Signal()
    game_stopped = Signal()

    def __init__(self, window, state):
        super().__init__(window)
        self.win, self.state = window, state
        self.watcher: LogWatchWorker | None = None
        self.game = GameWatcher(self.process_names())
        self.pending_url: str | None = None
        self.overlay = None
        self.poll_timer = QTimer(self); self.poll_timer.timeout.connect(self.poll)
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.timeout.connect(self._fire_import)
        self.remind_timer = QTimer(self); self.remind_timer.timeout.connect(self._remind); self.remind_timer.start(60_000)

    # ---------------------------------------------------------------- settings
    def process_names(self) -> list[str]:
        return parse_names(self.state.get("game_processes") or ", ".join(GAME_PROCESSES)) or GAME_PROCESSES

    def apply(self):
        """(Re)apply the settings: game detection, log watcher, overlay."""
        self.game.names = {n.lower() for n in self.process_names()}
        if self.state.get("game_detect"):
            if not self.poll_timer.isActive():
                self.poll_timer.start(POLL_MS)
            self.poll()
        else:
            self.poll_timer.stop()
            if self.game.running:                 # detection turned off mid-session
                self.game.running = False
                self.game.session = None
        self._update_watcher()
        self._update_overlay()
        self._emit_status()

    @property
    def in_game(self) -> bool:
        return bool(self.game.running)

    def _want_watcher(self) -> bool:
        if not self.state.get("auto_import"):
            return False
        return self.in_game if self.state.get("game_detect") else True

    def _update_watcher(self):
        want = self._want_watcher()
        if want and self.watcher is None:
            self.watcher = LogWatchWorker(self.state.get("game_dir") or None, interval=2.0 if self.in_game else 3.0)
            self.watcher.link_found.connect(self._link)
            self.watcher.status.connect(lambda s: self._emit_status(extra=s))
            self.watcher.start()
        elif not want and self.watcher is not None:
            self.stop_watcher()

    def stop_watcher(self):
        if self.watcher is not None:
            self.watcher.stop(); self.watcher.wait(2000)
            self.watcher = None

    def _emit_status(self, extra: str = ""):
        auto = self.state.get("auto_import")
        if self.in_game:
            text = "● Game running · auto-import on" if auto else "● Game running"
            tip = ("Open Convene → History in the game: new pulls are imported within seconds." if auto
                   else "Auto-import is off (Settings → Automation).")
        elif auto and self.state.get("game_detect"):
            text, tip = "○ Waiting for Wuthering Waves", "Auto-import starts when the game starts."
        elif auto:
            text, tip = "● Auto-import on", "Watching the game log."
        else:
            text, tip = "", ""
        if extra:
            tip += f"\n{extra}"
        self.status.emit(text, tip)

    # ---------------------------------------------------------------- game start / stop
    def poll(self):
        ev = self.game.poll()
        if ev == "started":
            self._on_started()
        elif ev == "stopped":
            self._on_stopped()

    def _on_started(self):
        self._update_watcher()
        self._update_overlay()
        self._emit_status()
        self.game_started.emit()
        if self.state.get("auto_import"):
            self.win.notify("Wuthering Waves started",
                            "Open Convene → History in the game and your new pulls are imported automatically.")
        if self.state.get("open_on_game"):
            self.win.show_window()

    def _on_stopped(self):
        s = self.game.last
        self._update_watcher()
        self._update_overlay()
        self._emit_status()
        self.game_stopped.emit()
        if s:
            if s.new_pulls:
                fives = f" 5★: {', '.join(s.five_stars)}." if s.five_stars else " No 5★ this time."
                self.win.notify("Session summary", f"{s.new_pulls} new pull(s) in {s.minutes:.0f} min.{fives}")
            elif self.state.get("sync_reminder") and self.state.get("auto_import") and s.minutes >= 5 and not s.imports:
                self.win.notify("Pulls not synced", "The game closed without opening Convene → History, so pulls from "
                                "this session (if any) aren't imported yet. Open it next time to sync.")
        if self.state.get("close_with_game"):
            QTimer.singleShot(4000, self.win.quit_app)

    def _remind(self):
        s = self.game.session
        if (s and not s.imports and not s.reminded and self.state.get("sync_reminder") and self.state.get("auto_import")
                and s.minutes >= REMIND_AFTER_MIN):
            s.reminded = True
            self.win.notify("Pulled something?", "Open Convene → History in the game to sync your pulls.")

    # ---------------------------------------------------------------- imports
    def _link(self, url: str):
        self.pending_url = url
        self.debounce.start(DEBOUNCE_MS)           # opening/closing the history quickly -> one import

    def _fire_import(self):
        url, self.pending_url = self.pending_url, None
        if not url:
            return
        gw = getattr(self.win, "gw", None)
        if gw is not None and gw.isRunning():       # an import is busy: try again once it's done
            self.pending_url = url
            self.debounce.start(DEBOUNCE_MS)
            return
        self.win.statusBar().showMessage("Convene history opened in the game: importing…", 8000)
        self.win.import_game(url=url, auto=True, retries=2)

    def imported(self, new_pulls: int, five_star_names: list[str]):
        s = self.game.session
        if s is not None:
            s.imports += 1
            s.new_pulls += new_pulls
            s.five_stars += five_star_names
        if self.overlay is not None:
            self.overlay.refresh()

    # ---------------------------------------------------------------- overlay
    def _update_overlay(self):
        want = bool(self.state.get("overlay")) and self.in_game
        if want and self.overlay is None:
            from .overlay import PullOverlay
            self.overlay = PullOverlay(self.state)
        if self.overlay is not None:
            self.overlay.setVisible(want)

    def shutdown(self):
        self.poll_timer.stop()
        self.stop_watcher()
        if self.overlay is not None:
            self.overlay.close()
