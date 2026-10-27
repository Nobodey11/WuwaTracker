"""Astrite income, the Astrite planner, the wishlist ("should I pull?") and "what if" scenarios.

Everything is exact (dynamic programming / convolution), like the probability engine.

Wishlist maths: after you get a featured 5★ the state is always reset (pity 0, no guarantee), so the pulls each
wish costs are independent random variables N_i. The first character wish starts from your real character-banner
pity/guarantee and the first weapon wish from your weapon-banner pity. Radiant Tides only work on character
banners and Forging Tides only on weapon banners; Astrite (as pulls) is shared. Pulling the wishes in order,
wishes 1..i all succeed iff  max(0, C_i - Tides) + max(0, W_i - Forging) <= shared pulls,
with C_i / W_i the summed pulls of the character / weapon wishes up to i.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from . import probability as pr
from .models import ASTRITE_PER_PULL

# Rough default income estimates (editable in the app; they differ per account and per patch)
DEFAULT_SOURCES = [
    {"name": "Daily activity", "astrite_per_day": 60, "on": True},
    {"name": "Lunite subscription", "astrite_per_day": 90, "on": False},
    {"name": "Tower / Whimpering Wastes / events (avg.)", "astrite_per_day": 60, "on": True},
]


# ---------------------------------------------------------------- income
def income_rate(entries: list[dict], today: date | None = None, window_days: int = 30) -> dict:
    """Average income per day over the last `window_days` days of logged entries."""
    today = today or date.today()
    start = today - timedelta(days=window_days - 1)
    recent = [e for e in entries if start <= date.fromisoformat(e["day"]) <= today]
    if not recent:
        return {"days": 0, "astrite_per_day": 0.0, "tides_per_day": 0.0, "forging_per_day": 0.0}
    first = min(date.fromisoformat(e["day"]) for e in recent)
    days = max(1, (today - first).days + 1)
    return {"days": days,
            "astrite_per_day": sum(e["astrite"] for e in recent) / days,
            "tides_per_day": sum(e.get("tides", 0) for e in recent) / days,
            "forging_per_day": sum(e.get("forging", 0) for e in recent) / days}


def income_by_month(entries: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in entries:
        m = e["day"][:7]
        d = out.setdefault(m, {"astrite": 0, "tides": 0, "forging": 0})
        d["astrite"] += e["astrite"]; d["tides"] += e.get("tides", 0); d["forging"] += e.get("forging", 0)
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- planner
@dataclass
class Plan:
    days: int
    astrite_at_target: int
    pulls: int
    leftover_astrite: int
    probability: float
    expected_copies: float
    pulls_for_50: int
    pulls_for_90: int
    curve: np.ndarray = field(repr=False, default=None)


def plan(h: np.ndarray, astrite: int, tides: int, target: date, astrite_per_day: float, extra_astrite: int = 0,
         tides_per_day: float = 0.0, copies: int = 1, pity: int = 0, guaranteed: bool = False,
         featured_chance: float = 0.5, today: date | None = None) -> Plan:
    today = today or date.today()
    days = max(0, (target - today).days)
    total = int(astrite + astrite_per_day * days + extra_astrite)
    pulls = total // ASTRITE_PER_PULL + int(tides + tides_per_day * days)
    res = pr.featured_distribution(h, pulls, copies, pity, guaranteed, featured_chance)
    return Plan(days=days, astrite_at_target=total, pulls=pulls, leftover_astrite=total % ASTRITE_PER_PULL,
                probability=res.probability, expected_copies=res.expected_featured,
                pulls_for_50=pr.pulls_needed(h, copies, 0.5, pity, guaranteed, featured_chance),
                pulls_for_90=pr.pulls_needed(h, copies, 0.9, pity, guaranteed, featured_chance),
                curve=res.curve)


def date_for_confidence(h, astrite, tides, astrite_per_day, confidence=0.9, copies=1, pity=0, guaranteed=False,
                        featured_chance=0.5, today: date | None = None, max_days=730) -> date | None:
    """First day on which the saved-up pulls reach `confidence` (None if never within max_days)."""
    today = today or date.today()
    need = pr.pulls_needed(h, copies, confidence, pity, guaranteed, featured_chance)
    have = astrite // ASTRITE_PER_PULL + tides
    if have >= need:
        return today
    if astrite_per_day <= 0:
        return None
    astrite_needed = (need - tides) * ASTRITE_PER_PULL - astrite
    days = int(np.ceil(astrite_needed / astrite_per_day))
    return today + timedelta(days=days) if days <= max_days else None


# ---------------------------------------------------------------- wishlist
@dataclass
class Wish:
    name: str
    kind: str = "character"     # "character" or "weapon"
    copies: int = 1


@dataclass
class WishResult:
    wishes: list[Wish]
    cumulative: list[float]          # P(wishes 1..i all obtained)
    alone: list[float]               # P(wish i) if every pull went to it alone
    expected_pulls: list[float]      # E[pulls] wish i costs on average
    drop_one: list[float]            # P(all OTHER wishes) if wish i is dropped
    budget_pulls: int
    tides: int
    forging: int

    @property
    def all(self) -> float:
        return self.cumulative[-1] if self.cumulative else 1.0

    def advice(self) -> str:
        if not self.wishes:
            return "Add a wish to see your odds."
        if self.budget_pulls + self.tides + self.forging == 0:
            return "Enter your Astrite and Tides above to see your odds."
        if self.all >= 0.9:
            return f"Very likely: {self.all:.0%} chance to get everything on the list."
        if len(self.wishes) == 1:
            return f"{self.all:.0%} chance. Save more, or lower the copies, to raise it."
        best = int(np.argmax(self.drop_one))
        if self.drop_one[best] <= self.all + 0.005:
            return f"{self.all:.0%} chance to get everything; dropping a wish barely helps, so you need more pulls."
        return (f"{self.all:.0%} chance to get everything. Dropping “{self.wishes[best].name}” helps most: "
                f"the rest then has {self.drop_one[best]:.0%}.")


def cost_pmf(h, copies, pity=0, guaranteed=False, featured_chance=0.5) -> np.ndarray:
    """pmf[n] = P(the copies-th featured 5★ lands exactly on pull n)."""
    max_n = int(copies * (2 if featured_chance < 1 else 1) * (len(h) - 1))
    curve = pr.featured_distribution(h, max_n, copies, pity, guaranteed, featured_chance).curve
    pmf = np.diff(curve, prepend=0.0)
    pmf[0] = 0.0
    return np.clip(pmf, 0, None)


def _cdf_at(cdf: np.ndarray, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x)
    out = np.where(x < 0, 0.0, cdf[np.clip(x, 0, len(cdf) - 1)])
    return np.where(x >= len(cdf) - 1, cdf[-1], out)


def _p_success(pc: np.ndarray, pw: np.ndarray, tides: int, forging: int, shared: int) -> float:
    """P(max(0, C - tides) + max(0, W - forging) <= shared) for independent C ~ pc, W ~ pw."""
    cdf_w = np.cumsum(pw)
    c = np.arange(len(pc))
    left = shared - np.maximum(0, c - tides)          # shared pulls left after the character wishes
    room = np.where(left >= 0, forging + left, -1)     # weapon wishes may use their own tides + what is left
    return float(np.sum(pc * _cdf_at(cdf_w, room)))


def wishlist(h_char, h_weap, wishes: list[Wish], budget_pulls: int, tides: int = 0, forging: int = 0,
             char_pity: int = 0, char_guaranteed: bool = False, weap_pity: int = 0,
             featured_chance_char: float = 0.5) -> WishResult:
    pmfs = []
    first_c = first_w = True
    for w in wishes:
        if w.kind == "weapon":
            pmfs.append(cost_pmf(h_weap, w.copies, weap_pity if first_w else 0, False, 1.0))
            first_w = False
        else:
            pmfs.append(cost_pmf(h_char, w.copies, char_pity if first_c else 0,
                                 char_guaranteed if first_c else False, featured_chance_char))
            first_c = False

    def run(idx: list[int]) -> list[float]:
        pc, pw = np.array([1.0]), np.array([1.0])
        out = []
        for i in idx:
            if wishes[i].kind == "weapon":
                pw = np.convolve(pw, pmfs[i])
            else:
                pc = np.convolve(pc, pmfs[i])
            out.append(_p_success(pc, pw, tides, forging, budget_pulls))
        return out

    cumulative = run(list(range(len(wishes))))
    alone = []
    for i, w in enumerate(wishes):
        own = tides if w.kind != "weapon" else forging
        alone.append(float(np.sum(pmfs[i][: own + budget_pulls + 1])))
    drop = []
    for i in range(len(wishes)):
        rest = [j for j in range(len(wishes)) if j != i]
        drop.append(run(rest)[-1] if rest else 1.0)
    exp = [float(np.sum(np.arange(len(p)) * p)) for p in pmfs]
    return WishResult(wishes, cumulative, alone, exp, drop, budget_pulls, tides, forging)


# ---------------------------------------------------------------- what if
def what_if_5050(results: list[str], overrides: dict[int, str]) -> dict:
    """Replay the character-banner 5★ sequence with some 50/50 outcomes changed.

    results   : the real sequence of 5★ results ("won", "lost", "guaranteed") in order
    overrides : index -> "won" / "lost" / "coin" (coin = a fair 50/50)
    A changed outcome changes the guarantee for the next 5★: a 5★ that really was guaranteed becomes a 50/50 if you
    hadn't lost before it, and a real 50/50 becomes guaranteed if you had lost before it.
    Returns expected featured copies (real and what-if) and the per-5★ chance of being featured.
    """
    pg = 0.0            # P(guaranteed) before the current 5★
    exp, per = 0.0, []
    for i, real in enumerate(results):
        o = overrides.get(i)
        if real == "guaranteed" and o is None:
            p_feat_ng = 0.5             # in the what-if world you weren't guaranteed: fair 50/50
        else:
            r = o or real
            p_feat_ng = {"won": 1.0, "lost": 0.0, "coin": 0.5}.get(r, 0.5)
        p = pg * 1.0 + (1 - pg) * p_feat_ng
        per.append(p)
        exp += p
        pg = (1 - pg) * (1 - p_feat_ng)          # lost a 50/50 -> next one guaranteed
    real_feat = sum(1 for r in results if r in ("won", "guaranteed"))
    return {"real_featured": real_featured_count(results), "whatif_featured": exp,
            "difference": exp - real_feat, "per_5star": per}


def real_featured_count(results: list[str]) -> int:
    return sum(1 for r in results if r in ("won", "guaranteed"))


def what_if_average_luck(h, featured: int, pulls_spent: int, featured_chance: float = 0.5) -> dict:
    """How many pulls an average player needs for the same number of featured copies."""
    if featured <= 0:
        return {"expected_pulls": 0.0, "your_pulls": pulls_spent, "saved_pulls": 0.0, "saved_astrite": 0}
    e = pr.expected_pulls_featured(h, 1, 0, False, featured_chance) * featured
    return {"expected_pulls": e, "your_pulls": pulls_spent, "saved_pulls": e - pulls_spent,
            "saved_astrite": int(round((e - pulls_spent) * ASTRITE_PER_PULL))}
