"""Is your luck statistically unusual?  Goodness-of-fit tests and Bayesian credible intervals (numpy only).

* KS test: largest gap between your pity distribution and the model's (p-value by Monte Carlo under the model).
* Chi-square test on pity bins (early / mid / soft pity), p-value by Monte Carlo too, so it is valid even for a
  small number of 5★s where the chi-square approximation breaks down.
* Bayesian fit: each pity's 5★ chance gets a Beta posterior (prior = the community curve, like the fitted model);
  sampling whole curves gives credible bands for the curve and for the consolidated rate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import probability as pr

BINS = [(1, 40), (41, 65), (66, 70), (71, 75), (76, 80)]


@dataclass
class LuckTest:
    n: int
    mean_pity: float
    model_mean: float
    ks_d: float
    ks_p: float
    chi2: float
    chi2_p: float
    observed: list[int]
    expected: list[float]
    verdict: str


def _model_pmf(h: np.ndarray) -> np.ndarray:
    pmf = pr.pity_pmf(h, 0)
    return pmf / pmf.sum()


def _ks(sample_counts: np.ndarray, cdf: np.ndarray) -> float:
    ecdf = np.cumsum(sample_counts) / sample_counts.sum()
    return float(np.max(np.abs(ecdf - cdf)))


def _chi2(counts_binned: np.ndarray, expected: np.ndarray) -> float:
    e = np.where(expected > 0, expected, 1e-12)
    return float(np.sum((counts_binned - expected) ** 2 / e))


def _bin(counts: np.ndarray) -> np.ndarray:
    return np.array([counts[a:b + 1].sum() for a, b in BINS], dtype=float)


def luck_test(pities: list[int], h: np.ndarray, sims: int = 4000, seed: int = 7) -> LuckTest | None:
    pities = [int(p) for p in pities if p > 0]
    n = len(pities)
    if n == 0:
        return None
    pmf = _model_pmf(h)
    HP = len(pmf) - 1
    cdf = np.cumsum(pmf)
    counts = np.bincount(np.clip(pities, 1, HP), minlength=HP + 1).astype(float)
    d_obs = _ks(counts, cdf)
    exp_b = _bin(pmf) * n
    obs_b = _bin(counts)
    c_obs = _chi2(obs_b, exp_b)
    rng = np.random.default_rng(seed)
    sim = rng.multinomial(n, pmf, size=sims).astype(float)          # sims x (HP+1)
    d_sim = np.max(np.abs(np.cumsum(sim, axis=1) / n - cdf), axis=1)
    sb = np.stack([sim[:, a:b + 1].sum(axis=1) for a, b in BINS], axis=1)
    c_sim = np.sum((sb - exp_b) ** 2 / np.where(exp_b > 0, exp_b, 1e-12), axis=1)
    ks_p = float((np.sum(d_sim >= d_obs - 1e-12) + 1) / (sims + 1))
    chi_p = float((np.sum(c_sim >= c_obs - 1e-12) + 1) / (sims + 1))
    mean = float(np.mean(pities))
    model_mean = float(np.sum(np.arange(HP + 1) * pmf))
    p = min(ks_p, chi_p)
    side = "luckier" if mean < model_mean else "unluckier"
    if n < 5:
        verdict = f"Only {n} 5★s: too few to say anything about luck yet."
    elif p < 0.01:
        verdict = (f"Unusual: your pity pattern is clearly {side} than the model (p = {p:.3f}). "
                   "Either real (un)luck or the soft-pity curve differs from the community estimate.")
    elif p < 0.05:
        verdict = f"Somewhat unusual: a bit {side} than the model (p = {p:.3f}), but not strong evidence."
    else:
        verdict = (f"Normal: your average pity {mean:.1f} vs. {model_mean:.1f} expected is well within normal "
                   f"variation (p = {p:.2f}). It's luck, not a rigged account.")
    return LuckTest(n, mean, model_mean, d_obs, ks_p, c_obs, chi_p, obs_b.astype(int).tolist(),
                    exp_b.round(2).tolist(), verdict)


@dataclass
class Bands:
    pity: np.ndarray
    low: np.ndarray       # 5 % quantile of h(n)
    mid: np.ndarray       # posterior median
    high: np.ndarray      # 95 % quantile
    rate_low: float       # consolidated 5★ rate interval
    rate_mid: float
    rate_high: float
    samples: np.ndarray   # draws x (HP+1) hazard curves


def bayes_bands(pities: list[int], censored: list[int], prior: np.ndarray, strength: float = 8.0,
                soft_start: int = 66, draws: int = 400, seed: int = 11) -> Bands:
    """Posterior Beta(strength*prior + d, strength*(1-prior) + r - d) per pity (pooled before soft pity)."""
    HP = len(prior) - 1
    d = np.zeros(HP + 1)
    r = np.zeros(HP + 1)
    for n in range(1, HP + 1):
        d[n] = sum(1 for p in pities if p == n)
        r[n] = sum(1 for p in pities if p >= n) + sum(1 for c in censored if c >= n)
    rng = np.random.default_rng(seed)
    S = np.zeros((draws, HP + 1))
    n_flat = soft_start - 1
    a = strength * n_flat * prior[1] + d[1:soft_start].sum()
    b = strength * n_flat * (1 - prior[1]) + (r[1:soft_start] - d[1:soft_start]).sum()
    S[:, 1:soft_start] = rng.beta(a, max(b, 1e-6), size=draws)[:, None]
    for n in range(soft_start, HP):
        p0 = min(max(prior[n], 1e-6), 1 - 1e-6)
        S[:, n] = rng.beta(strength * p0 + d[n], max(strength * (1 - p0) + r[n] - d[n], 1e-6), size=draws)
    S[:, HP] = 1.0
    rates = np.array([pr.consolidated_rate(S[i]) for i in range(draws)])
    q = lambda arr, x: np.quantile(arr, x, axis=0)
    return Bands(np.arange(HP + 1), q(S, 0.05), q(S, 0.5), q(S, 0.95),
                 float(np.quantile(rates, 0.05)), float(np.median(rates)), float(np.quantile(rates, 0.95)), S)


def probability_interval(bands: Bands, pulls: int, copies: int = 1, pity: int = 0, guaranteed: bool = False,
                         featured_chance: float = 0.5, max_draws: int = 120) -> tuple[float, float, float]:
    """5 / 50 / 95 % interval of P(>= copies featured within pulls) over the posterior curves."""
    vals = [pr.featured_distribution(s, pulls, copies, pity, guaranteed, featured_chance).probability
            for s in bands.samples[:max_draws]]
    return float(np.quantile(vals, 0.05)), float(np.median(vals)), float(np.quantile(vals, 0.95))
