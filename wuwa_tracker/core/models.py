"""Data model and static game knowledge."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

ASTRITE_PER_PULL = 160

# NOTE: patch-dependent knowledge (banner names, standard 5★ list, rates, banner calendar) lives in
# wuwa_tracker/data/game_data.json and is loaded through core/gamedata.py so it can be updated every patch.

HARD_PITY_5 = 80
HARD_PITY_4 = 10


@dataclass(frozen=True)
class Pull:
    pool_type: int
    resource_id: int
    quality: int
    name: str
    time: datetime
    group: int = 0
    player_id: str = ""

    @property
    def sort_key(self):
        return (self.time, self.group)

    @property
    def key(self):
        """Unique identity used for de-duplication."""
        return (self.player_id, self.pool_type, self.time.isoformat(), self.group, self.resource_id)


@dataclass
class FiveStarEvent:
    name: str
    pity: int
    time: datetime
    pull_number: int            # 1-based index on that banner
    result: str = ""            # "won", "lost", "guaranteed" or "" (non-50/50 banner)
    resource_id: int = 0        # game id (weapons >= 100000), used for portraits


@dataclass
class BannerStats:
    pool_type: int
    name: str
    total_pulls: int = 0
    pity5: int = 0
    pity4: int = 0
    count5: int = 0
    count4: int = 0
    five_stars: list[FiveStarEvent] = field(default_factory=list)
    guaranteed: bool = False     # next 5★ guaranteed featured (char banner)
    kind: str = "event"          # banner kind from game data
    has_5050: bool = False       # featured_character banner
    featured_chance: float | None = None  # 0.5 char banner, 1.0 weapon banner, None otherwise
    wins: int = 0
    losses: int = 0
    first_pull: datetime | None = None
    last_pull: datetime | None = None

    @property
    def astrite(self) -> int:
        return self.total_pulls * ASTRITE_PER_PULL

    @property
    def avg_pity5(self) -> float | None:
        if not self.five_stars:
            return None
        return sum(f.pity for f in self.five_stars) / len(self.five_stars)

    @property
    def avg_featured_pity(self) -> float | None:
        """Pulls spent per featured 5★ (what wuwatracker calls average featured pity)."""
        featured = [f for f in self.five_stars if f.result in ("won", "guaranteed", "")]
        if not featured:
            return None
        spent = sum(f.pity for f in self.five_stars[: self.five_stars.index(featured[-1]) + 1])
        return spent / len(featured)

    @property
    def win_rate(self) -> float | None:
        n = self.wins + self.losses
        return self.wins / n if n else None

    @property
    def rate5(self) -> float:
        return self.count5 / self.total_pulls if self.total_pulls else 0.0

    def to_dict(self) -> dict:
        """Compact summary, used for the AI assistant."""
        return {
            "banner": self.name,
            "pool_type": self.pool_type,
            "kind": self.kind,
            "total_pulls": self.total_pulls,
            "astrite_spent": self.astrite,
            "current_5star_pity": self.pity5,
            "current_4star_pity": self.pity4,
            "next_5star_guaranteed_featured": self.guaranteed if self.has_5050 else None,
            "five_star_count": self.count5,
            "four_star_count": self.count4,
            "avg_5star_pity": round(self.avg_pity5, 2) if self.avg_pity5 else None,
            "fifty_fifty_wins": self.wins,
            "fifty_fifty_losses": self.losses,
            "five_stars": [
                {"name": f.name, "pity": f.pity, "date": f.time.date().isoformat(), "result": f.result or None}
                for f in self.five_stars
            ],
        }
