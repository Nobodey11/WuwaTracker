"""Turn a list of pulls into per-banner statistics (pity, 50/50, history)."""
from __future__ import annotations

from collections import defaultdict

from .gamedata import GameData
from .models import BannerStats, FiveStarEvent, Pull

_DEFAULT_GD: GameData | None = None


def default_gamedata() -> GameData:
    """Bundled game data only (used by tests / when no app state is available)."""
    global _DEFAULT_GD
    if _DEFAULT_GD is None:
        import json
        from .gamedata import BUNDLED
        _DEFAULT_GD = GameData(json.loads(BUNDLED.read_text(encoding="utf-8")))
    return _DEFAULT_GD


def group_by_banner(pulls: list[Pull]) -> dict[int, list[Pull]]:
    out: dict[int, list[Pull]] = defaultdict(list)
    for p in pulls:
        out[p.pool_type].append(p)
    for v in out.values():
        v.sort(key=lambda p: p.sort_key)
    return dict(sorted(out.items()))


def banner_stats(pool_type: int, pulls: list[Pull], gd: GameData | None = None) -> BannerStats:
    """pulls must be chronological (oldest first) and belong to one banner type."""
    gd = gd or default_gamedata()
    standard = gd.standard_resonators
    s = BannerStats(pool_type=pool_type, name=gd.name(pool_type), kind=gd.kind(pool_type),
                    has_5050=gd.has_5050(pool_type), featured_chance=gd.featured_chance(pool_type))
    is_char_event = s.has_5050
    for i, p in enumerate(pulls, start=1):
        s.total_pulls += 1
        s.pity5 += 1
        s.pity4 += 1
        if p.quality == 5:
            result = ""
            if is_char_event:
                if p.name in standard:
                    result = "lost"
                    s.losses += 1
                    s.guaranteed = True
                elif s.guaranteed:
                    result = "guaranteed"
                    s.guaranteed = False
                else:
                    result = "won"
                    s.wins += 1
            s.five_stars.append(FiveStarEvent(p.name, s.pity5, p.time, i, result))
            s.count5 += 1
            s.pity5 = 0
            s.pity4 = 0          # a 5★ also resets the 4★ counter (matches wuwatracker)
        elif p.quality == 4:
            s.count4 += 1
            s.pity4 = 0
    if pulls:
        s.first_pull, s.last_pull = pulls[0].time, pulls[-1].time
    return s


def all_stats(pulls: list[Pull], gd: GameData | None = None) -> dict[int, BannerStats]:
    return {pt: banner_stats(pt, ps, gd) for pt, ps in group_by_banner(pulls).items()}


def pity_observations(stats: BannerStats) -> tuple[list[int], int]:
    """(list of pity values at which a 5★ dropped, current censored pity) for hazard fitting."""
    return [f.pity for f in stats.five_stars], stats.pity5


def pity_with_rows(pulls: list[Pull]) -> list[tuple[Pull, int]]:
    """Each pull with its 5★ pity counter at the time of the pull (for the history table)."""
    out = []
    pity = defaultdict(int)
    for p in sorted(pulls, key=lambda p: (p.pool_type, p.time, p.group)):
        pity[p.pool_type] += 1
        out.append((p, pity[p.pool_type]))
        if p.quality == 5:
            pity[p.pool_type] = 0
    return out


def pity_with_rows_4(pulls: list[Pull]) -> dict[tuple, int]:
    """Map pull.key -> 4★ pity counter at the time of that pull."""
    out = {}
    pity = defaultdict(int)
    for p in sorted(pulls, key=lambda p: (p.pool_type, p.time, p.group)):
        pity[p.pool_type] += 1
        out[p.key] = pity[p.pool_type]
        if p.quality >= 4:
            pity[p.pool_type] = 0
    return out
