"""Shared application state: storage, current player, game data, computed stats, settings."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..core import probability as pr
from ..core.analysis import all_stats
from ..core.gamedata import GameData, GameDataStore
from ..core.models import BannerStats, Pull
from ..core.storage import Storage

DEFAULTS = {
    "ollama_host": "http://localhost:11434",
    "ollama_model": "",
    "game_dir": "",
    "server_region": "Asia",   # your wuwatracker reset timers match the Asia server (UTC+8)
    "pity_model": "community",
    "player": "",
    # Raw URL of a game_data.json you keep up to date (e.g. on GitHub). Checked on start-up.
    "gamedata_url": "https://raw.githubusercontent.com/Nobodey11/WuwaTracker/main/wuwa_tracker/data/game_data.json",
    "gamedata_autocheck": True,
    "prydwen_enabled": True,      # tier list, character info and portraits from prydwen.gg
    "extra_owned": {},            # characters/weapons owned outside of pulls (gifts, free units): name -> copies
    "redeemed_codes": [],         # redemption codes the user ticked as redeemed
    "seen_codes": [],             # codes already shown once (for the "new code" alert)
    # 0.6 – 1.0
    "update_check": True,         # look for a newer app version on GitHub (max once a day)
    "last_update_check": 0.0,
    "auto_import": False,         # watch the game log and import as soon as Convene → History is opened
    "tray": True,                 # tray icon with reset timers and quick actions
    "close_to_tray": False,       # closing the window keeps the app running in the tray
    "notify_codes": True,
    "notify_banners": True,
    "notify_imports": True,
    "notified": [],               # notification ids already shown (banner-ending alerts)
    "persona": "analyst",
    "weekly_summary": True,
    "last_summary_week": "",
    "user_events": [],            # [{name, start, end, note}]
    "income_sources": [],         # planner estimate sources (empty = defaults)
    "planner": {},                # last planner inputs
    "wishlist": [],               # [{name, kind, copies}]
    "sim_achievements": [],
    "sim_board": [],
    # 1.1: start with Windows / the game
    "game_detect": True,          # notice when Wuthering Waves starts and stops
    "game_processes": "",         # empty = defaults (Client-Win64-Shipping.exe, Wuthering Waves.exe)
    "open_on_game": False,        # open the window when the game starts (else stay in the tray)
    "overlay": True,              # small always-on-top pity/odds overlay during the game
    "overlay_pos": None,
    "sync_reminder": True,        # remind to open Convene → History when nothing was imported
    "close_with_game": False,     # quit the tracker when the game closes
    "v11_setup": False,           # first start of 1.1 done (turns on auto-import + start with Windows once)
}

# Optional local file next to the app (git-ignored) with extra owned characters, e.g. {"Rebecca": 1}.
# It is merged into the saved list on start-up, so it can be edited by hand too.
LOCAL_EXTRAS = Path(__file__).resolve().parents[2] / "my_characters.json"

# Banner kinds that share the normal 5★ rate table (used to fit the curve on your own data)
FIT_KINDS = ("featured_character", "featured_weapon", "standard", "event")


class AppState(QObject):
    changed = Signal()
    new_content = Signal(list, list)     # unknown 5★ items, unknown banner types

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.pulls: list[Pull] = []
        self.stats: dict[int, BannerStats] = {}
        # in-memory settings cache: background threads (AI assistant) must not touch SQLite
        self._settings = {k: storage.get_setting(k, v) for k, v in DEFAULTS.items()}
        self._merge_local_extras()
        self.gd_store = GameDataStore(storage.path.parent)
        from ..core.prydwen import Prydwen
        from .images import ImageLoader
        self.prydwen = Prydwen(storage.path.parent / "prydwen")
        self.images = ImageLoader(self.prydwen, self.prydwen_on)
        self.gd: GameData = self.gd_store.load()
        self.reload()

    # settings helpers
    def get(self, key):
        return self._settings.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._settings[key] = value
        self.storage.set_setting(key, value)

    @property
    def player(self) -> str:
        players = self.storage.players()
        p = self.get("player")
        if p not in players:
            p = players[0] if players else ""
        return p

    @property
    def data_dir(self) -> Path:
        return self.storage.path.parent

    @property
    def notes_dir(self) -> Path:
        d = self.data_dir / "notes"
        d.mkdir(exist_ok=True)
        return d

    def nickname(self, player: str | None = None) -> str:
        player = player if player is not None else self.player
        return self.storage.nicknames().get(player, "")

    def income_entries(self) -> list[dict]:
        return self.storage.income(self.player)

    def income_rate(self) -> dict:
        """Logged income (if at least a week of entries), else the estimate from the planner's sources."""
        from ..core import planner
        r = planner.income_rate(self.income_entries())
        if r["days"] >= 7:
            r["source"] = "logged"
            return r
        srcs = self.get("income_sources") or planner.DEFAULT_SOURCES
        return {"days": 0, "astrite_per_day": float(sum(s["astrite_per_day"] for s in srcs if s.get("on"))),
                "tides_per_day": 0.0, "forging_per_day": 0.0, "source": "estimate"}

    def prydwen_on(self) -> bool:
        return bool(self.get("prydwen_enabled"))

    def owned(self) -> dict[str, int]:
        """normalised name -> copies owned: pulled 4★/5★ plus extras (gifts / free units)."""
        from ..core.prydwen import key
        out: dict[str, int] = {}
        for p in self.pulls:
            if p.quality >= 4:
                out[key(p.name)] = out.get(key(p.name), 0) + 1
        from ..core.collection import ROVERS, is_rover
        rovers = set(ROVERS) | {c["name"] for c in self.prydwen.cached_character_list().values() if is_rover(c["name"])}
        tl = self.prydwen.cached_tier_list()
        if tl:
            rovers |= {e.name for e in tl.entries if is_rover(e.name)}
        for r in rovers:                      # the Rover is always owned
            out[key(r)] = out.get(key(r), 0) + 1
        for name, n in (self.get("extra_owned") or {}).items():
            out[key(name)] = out.get(key(name), 0) + int(n)
        return out

    # ---- extra owned (not from pulls)
    def extras(self) -> dict[str, int]:
        return dict(self.get("extra_owned") or {})

    def set_extra(self, name: str, copies: int):
        ex = self.extras()
        if copies > 0:
            ex[name] = int(copies)
        else:
            ex.pop(name, None)
        self.set("extra_owned", ex)
        self._write_local_extras(ex)
        self.reload()

    def _merge_local_extras(self):
        try:
            data = json.loads(LOCAL_EXTRAS.read_text(encoding="utf-8")) if LOCAL_EXTRAS.exists() else {}
        except (OSError, json.JSONDecodeError):
            return
        ex = dict(self._settings.get("extra_owned") or {})
        changed = False
        for name, n in data.items():
            if isinstance(n, int) and n > ex.get(name, 0):
                ex[name] = n
                changed = True
        if changed:
            self.set("extra_owned", ex)

    @staticmethod
    def _write_local_extras(ex):
        try:
            LOCAL_EXTRAS.write_text(json.dumps(ex, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def reload_gamedata(self):
        self.gd = self.gd_store.load()
        self.reload()

    def reload(self):
        self.pulls = self.storage.load(self.player or None)
        self.stats = all_stats(self.pulls, self.gd)
        self.owned_snapshot = self.owned()      # read by the AI worker thread
        self.changed.emit()

    def unknown_content(self):
        return self.gd.find_unknown(self.pulls)

    def hazard(self, model: str | None = None):
        model = model or self.get("pity_model")
        rates = self.gd.rates
        if model == "fitted":
            pities, cens = [], []
            for pt, s in self.stats.items():
                if s.kind in FIT_KINDS:
                    pities += [f.pity for f in s.five_stars]
                    cens.append(s.pity5)
            steps = rates.get("soft_pity_steps") or [[66, 0]]
            return pr.hazard_fitted(pities, cens, prior=pr.hazard_community(rates), soft_start=steps[0][0])
        fn = pr.MODELS.get(model, pr.MODELS["community"])[1]
        return fn(rates)
