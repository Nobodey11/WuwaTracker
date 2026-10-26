"""Shared application state: storage, current player, game data, computed stats, settings."""
from __future__ import annotations

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
}

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

    def prydwen_on(self) -> bool:
        return bool(self.get("prydwen_enabled"))

    def owned(self) -> dict[str, int]:
        """normalised name -> number of copies pulled (characters and weapons)."""
        from ..core.prydwen import key
        out: dict[str, int] = {}
        for p in self.pulls:
            if p.quality >= 4:
                out[key(p.name)] = out.get(key(p.name), 0) + 1
        return out

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
