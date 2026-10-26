"""Exact probability engine for WuWa Convenes.

The 5★ chance on each pull depends only on the current pity (pulls since the last 5★).
That per-pull chance is called the *hazard* h(n) for pull number n = 1..80.

Kuro publishes: base 0.8 %, soft pity from ~66, hard pity 80. The exact curve after 66
is NOT official, so several models are provided plus a model fitted on your own pulls.

All calculations are exact dynamic programming over the state
(pity, guaranteed, featured copies) — no Monte-Carlo noise.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import ASTRITE_PER_PULL

BASE_RATE_5 = 0.008
SOFT_START = 66


def _default_rates() -> dict:
    from .analysis import default_gamedata
    return default_gamedata().rates


def hazard_community(rates: dict | None = None) -> np.ndarray:
    """Soft-pity curve built from game data `rates` (default: +4 %/pull from 66, +8 % from 71,
    +10 % from 76, 100 % at 80). Index 0 is unused; h[n] = chance that pull n (pity n) is a 5★.
    Each patch you can change `rates.soft_pity_steps` in game_data.json without touching code."""
    rates = rates or _default_rates()
    base, hard = rates["base5"], int(rates["hard_pity5"])
    steps = sorted(rates["soft_pity_steps"])
    h = np.zeros(hard + 1)
    for n in range(1, hard + 1):
        r = base
        for i, (start, inc) in enumerate(steps):
            stop = steps[i + 1][0] if i + 1 < len(steps) else hard
            if n >= start:
                r += inc * (min(n, stop - 1) - start + 1)
        h[n] = min(r, 1.0)
    h[hard] = 1.0
    return h


def hazard_flat(rates: dict | None = None) -> np.ndarray:
    """Pessimistic lower bound: base rate flat, only hard pity."""
    rates = rates or _default_rates()
    hard = int(rates["hard_pity5"])
    h = np.full(hard + 1, rates["base5"])
    h[0] = 0
    h[hard] = 1.0
    return h


def hazard_fitted(pities: list[int], censored: list[int] | None = None, prior: np.ndarray | None = None,
                  strength: float = 8.0, soft_start: int = SOFT_START) -> np.ndarray:
    """Kaplan-Meier style hazard from observed 5★ pities, smoothed with a Beta prior.

    pities   : pity values at which a 5★ dropped (all banners sharing the same rates)
    censored : current unfinished pity counters (pulls that did NOT yet hit a 5★)
    prior    : prior hazard curve (default: community model)
    strength : prior pseudo-count — higher = trust the prior more where data is thin

    h_fit(n) = (d_n + strength * h_prior(n)) / (r_n + strength)
    where d_n = #5★ at pity n, r_n = #cycles that reached pity n (risk set).
    """
    prior = hazard_community() if prior is None else prior
    HP = len(prior) - 1
    SOFT_START = soft_start
    censored = censored or []
    d = np.zeros(HP + 1)
    r = np.zeros(HP + 1)
    for n in range(1, HP + 1):
        d[n] = sum(1 for p in pities if p == n)
        r[n] = sum(1 for p in pities if p >= n) + sum(1 for c in censored if c >= n)
    h = np.zeros(HP + 1)
    # Before soft pity the rate is constant by design, so pool pulls 1..SOFT_START-1 into one estimate
    # (avoids noisy spikes from single lucky early pulls).
    flat = slice(1, SOFT_START)
    n_flat = SOFT_START - 1
    h[flat] = (d[flat].sum() + strength * n_flat * prior[1]) / (r[flat].sum() + strength * n_flat)
    for n in range(SOFT_START, HP):
        h[n] = (d[n] + strength * prior[n]) / (r[n] + strength)
    h[HP] = 1.0
    return h


MODELS = {
    "community": ("Community estimate (soft pity 66+)", hazard_community),
    "flat": ("Flat 0.8 % + hard pity (worst case)", hazard_flat),
}


def pity_pmf(h: np.ndarray, start_pity: int = 0) -> np.ndarray:
    """P(next 5★ lands exactly k pulls from now), k = 1..(80 - start_pity). Index 0 unused."""
    n_max = len(h) - 1 - start_pity
    pmf = np.zeros(n_max + 1)
    survive = 1.0
    for k in range(1, n_max + 1):
        hk = h[start_pity + k]
        pmf[k] = survive * hk
        survive *= 1 - hk
    return pmf


def expected_pulls_5star(h: np.ndarray, start_pity: int = 0) -> float:
    pmf = pity_pmf(h, start_pity)
    return float(sum(k * pmf[k] for k in range(len(pmf))))


def consolidated_rate(h: np.ndarray) -> float:
    """Long-run 5★ rate per pull (= 1 / expected pulls per 5★)."""
    return 1.0 / expected_pulls_5star(h, 0)


@dataclass
class FeaturedResult:
    pulls: int
    copies: int
    probability: float                 # P(>= copies featured within `pulls`)
    curve: np.ndarray                  # curve[n] = P(>= copies featured within n pulls), n=0..pulls
    copies_dist: np.ndarray            # P(exactly c featured) for c=0..copies (last = >= copies)
    expected_featured: float
    astrite: int


def featured_distribution(h: np.ndarray, pulls: int, copies: int = 1, pity: int = 0,
                          guaranteed: bool = False, featured_chance: float = 0.5) -> FeaturedResult:
    """Exact DP.

    featured_chance: chance a non-guaranteed 5★ is the featured one (0.5 for the
    character banner; 1.0 for the featured weapon banner).
    State tensor P[pity, g, c]: pity 0..79, g = guaranteed flag, c = copies (capped at `copies`).
    """
    copies = max(1, copies)
    HP = len(h) - 1
    P = np.zeros((HP, 2, copies + 1))
    P[min(pity, HP - 1), int(guaranteed), 0] = 1.0
    curve = np.zeros(pulls + 1)
    exp_feat = np.zeros(pulls + 1)  # expected copies (uncapped tracked separately)
    exp_total = 0.0
    hz = h[1:HP + 1]       # hz[p] = chance at next pull when current pity = p
    for n in range(1, pulls + 1):
        Q = np.zeros_like(P)
        hit = P * hz[:, None, None]            # mass that gets a 5★ this pull
        miss = P - hit
        Q[1:] += miss[:-1]                     # pity +1 (pity 79 always hits since h[80]=1)
        hit_total = hit.sum(axis=0)            # [g, c] at pity -> 0
        # guaranteed: always featured
        g1 = hit_total[1]
        Q[0, 0, 1:] += g1[:-1]
        Q[0, 0, -1] += g1[-1]
        exp_total += g1.sum()
        # 50/50
        g0 = hit_total[0]
        win = g0 * featured_chance
        lose = g0 * (1 - featured_chance)
        Q[0, 0, 1:] += win[:-1]
        Q[0, 0, -1] += win[-1]
        exp_total += win.sum()
        Q[0, 1, :] += lose
        P = Q
        curve[n] = P[:, :, -1].sum()
    dist = P.sum(axis=(0, 1))
    return FeaturedResult(pulls=pulls, copies=copies, probability=float(curve[pulls]) if pulls else 0.0,
                          curve=curve, copies_dist=dist, expected_featured=float(exp_total),
                          astrite=pulls * ASTRITE_PER_PULL)


def pulls_needed(h: np.ndarray, copies: int = 1, confidence: float = 0.9, pity: int = 0,
                 guaranteed: bool = False, featured_chance: float = 0.5) -> int:
    """Smallest N so that P(>= copies featured within N pulls) >= confidence."""
    max_n = int(copies * 2 * (len(h) - 1))
    res = featured_distribution(h, max_n, copies, pity, guaranteed, featured_chance)
    idx = np.argmax(res.curve >= confidence - 1e-12)
    return int(idx) if res.curve[idx] >= confidence - 1e-12 else max_n


def expected_pulls_featured(h: np.ndarray, copies: int = 1, pity: int = 0, guaranteed: bool = False,
                            featured_chance: float = 0.5) -> float:
    """E[pulls until `copies` featured] = sum_n P(not yet done after n pulls)."""
    max_n = int(copies * 2 * (len(h) - 1))
    res = featured_distribution(h, max_n, copies, pity, guaranteed, featured_chance)
    return float(np.sum(1.0 - res.curve[:max_n]))


def luck_percentile(h: np.ndarray, observed_pities: list[int]) -> float | None:
    """Share of players (under the model) with a *lower* average 5★ pity than you over the same
    number of 5★s. Low = lucky. Computed by convolving the per-5★ pity pmf."""
    k = len(observed_pities)
    if k == 0:
        return None
    pmf = pity_pmf(h, 0)
    total = np.array([1.0])
    for _ in range(k):
        total = np.convolve(total, pmf)
    obs = sum(observed_pities)
    return float(total[:obs].sum() + 0.5 * total[obs])


def hazard_4star(rates: dict | None = None) -> np.ndarray:
    """Chance of a 4★-or-better per pull by 4★ pity: base rate, guaranteed at hard pity (10)."""
    rates = rates or _default_rates()
    hard = int(rates.get("hard_pity4", 10))
    h = np.full(hard + 1, rates.get("base4", 0.06))
    h[0] = 0
    h[hard] = 1.0
    return h


def next_pulls(h: np.ndarray, pity5: int, guaranteed: bool, featured_chance: float | None,
               pity4: int = 0, rates: dict | None = None, horizons=(1, 10)) -> dict[int, dict]:
    """Odds for the very next pulls from the current state.

    For each horizon n returns:
      any5      P(at least one 5★ in the next n pulls)
      featured  P(at least one *featured* 5★) (50/50 + guarantee aware; None for non-featured banners)
      four_plus P(at least one 4★ or better)
    """
    h4 = hazard_4star(rates)
    hard4 = len(h4) - 1
    out = {}
    for n in horizons:
        # any 5★: survive n pulls without a 5★ (pity can't wrap before the first hit)
        surv5, p = 1.0, pity5
        for _ in range(n):
            p += 1
            surv5 *= 1 - h[min(p, len(h) - 1)]
        # 4★+: a 4★ OR a 5★ ends the dry streak; once a 5★/4★ hits, the guarantee is met anyway
        surv4, p4, p5 = 1.0, pity4, pity5
        for _ in range(n):
            p4 += 1; p5 += 1
            surv4 *= (1 - h4[min(p4, hard4)]) * (1 - h[min(p5, len(h) - 1)])
        feat = None
        if featured_chance is not None:
            feat = featured_distribution(h, n, 1, pity5, guaranteed, featured_chance).probability
        out[n] = {"any5": float(1 - surv5), "featured": None if feat is None else float(feat),
                  "four_plus": float(1 - surv4)}
    return out
