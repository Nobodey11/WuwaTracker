"""Convene simulator (mini-game). Uses the same rates as the probability engine:
soft-pity 5★ curve, 4★ guarantee every 10, 50/50 + guarantee on the character banner,
100 % featured 5★ on the weapon banner, and a 50 % chance for a 4★ to be one of the featured 4★s.
Purely for fun: no real Astrite is spent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

FALLBACK_4_RES = ["Danjin", "Chixia", "Lumi", "Taoqi", "Yuanwu", "Mortefi", "Sanhua", "Aalto", "Yangyang", "Baizhi",
                  "Youhu", "Buling"]
FALLBACK_4_WEAP = ["Lunar Cutter", "Hollow Mirage", "Commando of Conviction", "Cadenza", "Variation", "Undying Flame"]
FALLBACK_3 = ["Originite: Type IV", "Sword of Night", "Broadblade of Night", "Pistols of Night", "Gauntlets of Night",
              "Rectifier of Night", "Pistols of Voyager"]


@dataclass
class SimItem:
    name: str
    rarity: int
    is_weapon: bool = False
    resource_id: int | None = None
    featured: bool = False
    pity: int = 0                 # pulls it took (5★ pity / 4★ pity)
    result: str = ""              # 5★ on char banner: "won" / "lost" / "guaranteed"


@dataclass
class SimStats:
    pulls: int = 0
    five: int = 0
    featured5: int = 0
    four: int = 0
    wins: int = 0
    losses: int = 0
    five_pities: list[int] = field(default_factory=list)
    history: list[SimItem] = field(default_factory=list)   # 4★ and 5★ only


class ConveneSim:
    def __init__(self, hazard, rates: dict, weapon_banner: bool, featured5: str,
                 standard5: list[str], featured4: list[str] | None = None,
                 pool4: list[tuple[str, int | None, bool]] | None = None,
                 pool3: list[tuple[str, int | None]] | None = None,
                 pity5: int = 0, pity4: int = 0, guaranteed: bool = False,
                 featured5_rid: int | None = None, seed: int | None = None):
        self.h = hazard
        self.rates = rates
        self.weapon_banner = weapon_banner
        self.featured5 = featured5
        self.featured5_rid = featured5_rid
        self.standard5 = list(standard5) or ["Verina"]
        self.featured4 = list(featured4 or [])
        self.pool4 = list(pool4 or []) or [(n, None, False) for n in FALLBACK_4_RES] + [(n, None, True) for n in FALLBACK_4_WEAP]
        self.pool3 = list(pool3 or []) or [(n, None) for n in FALLBACK_3]
        self.pity5, self.pity4, self.guaranteed = pity5, pity4, guaranteed
        self.rng = random.Random(seed)
        self.stats = SimStats()

    @property
    def hard4(self) -> int:
        return int(self.rates.get("hard_pity4", 10))

    @property
    def astrite(self) -> int:
        return self.stats.pulls * int(self.rates.get("astrite_per_pull", 160))

    def _five(self) -> SimItem:
        pity = self.pity5
        if self.weapon_banner:
            item = SimItem(self.featured5, 5, True, self.featured5_rid, True, pity)
        elif self.guaranteed or self.rng.random() < self.rates.get("featured_chance_character", 0.5):
            item = SimItem(self.featured5, 5, False, None, True, pity, "guaranteed" if self.guaranteed else "won")
            if not self.guaranteed:
                self.stats.wins += 1
            self.guaranteed = False
        else:
            item = SimItem(self.rng.choice(self.standard5), 5, False, None, False, pity, "lost")
            self.stats.losses += 1
            self.guaranteed = True
        self.stats.five += 1
        self.stats.featured5 += item.featured
        self.stats.five_pities.append(pity)
        return item

    def _four(self) -> SimItem:
        pity = self.pity4
        feat = [n for n in self.featured4]
        if feat and self.rng.random() < 0.5:
            name = self.rng.choice(feat)
            match = next((p for p in self.pool4 if p[0] == name), None)
            item = SimItem(name, 4, match[2] if match else False, match[1] if match else None, True, pity)
        else:
            others = [p for p in self.pool4 if p[0] not in feat] or self.pool4
            name, rid, is_w = self.rng.choice(others)
            item = SimItem(name, 4, is_w, rid, False, pity)
        self.stats.four += 1
        return item

    def pull_one(self) -> SimItem:
        self.stats.pulls += 1
        self.pity5 += 1
        self.pity4 += 1
        h5 = self.h[min(self.pity5, len(self.h) - 1)]
        if self.rng.random() < h5:
            item = self._five()
            self.pity5 = 0
            self.pity4 = 0
        elif self.pity4 >= self.hard4 or self.rng.random() < self.rates.get("base4", 0.06):
            item = self._four()
            self.pity4 = 0
        else:
            name, rid = self.rng.choice(self.pool3)
            item = SimItem(name, 3, True, rid, False, 0)
        if item.rarity >= 4:
            self.stats.history.append(item)
        return item

    def pull(self, n: int = 1) -> list[SimItem]:
        return [self.pull_one() for _ in range(n)]


def pools_from_pulls(pulls) -> tuple[list, list, dict]:
    """Build realistic 4★/3★ pools from the user's own history. Returns (pool4, pool3, name->resource_id)."""
    pool4, pool3, rids = {}, {}, {}
    for p in pulls:
        rids[p.name] = p.resource_id
        if p.quality == 4:
            pool4[p.name] = (p.name, p.resource_id, p.resource_id >= 100000)
        elif p.quality == 3:
            pool3[p.name] = (p.name, p.resource_id)
    return list(pool4.values()), list(pool3.values()), rids
