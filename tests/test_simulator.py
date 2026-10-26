"""The mini-game must follow the same rules/odds as the probability engine."""
import numpy as np

from wuwa_tracker.core import probability as pr
from wuwa_tracker.core.analysis import default_gamedata
from wuwa_tracker.core.simulator import ConveneSim

RATES = default_gamedata().rates


def sim(**kw):
    return ConveneSim(pr.hazard_community(RATES), RATES, kw.pop("weapon", False), "Suoming",
                      ["Calcharo", "Encore"], ["Lumi", "Danjin", "Chixia"], seed=kw.pop("seed", 1), **kw)


def test_hard_pity_and_four_star_guarantee():
    s = sim()
    items = s.pull(20000)
    run5 = run4 = 0
    for it in items:
        run5 += 1; run4 += 1
        if it.rarity == 5:
            assert run5 <= 80; run5 = 0; run4 = 0
        elif it.rarity == 4:
            assert run4 <= 10; run4 = 0
        assert run4 <= 10


def test_rates_match_probability_engine():
    s = sim(seed=7)
    s.pull(200_000)
    expected = pr.consolidated_rate(pr.hazard_community(RATES))
    assert abs(s.stats.five / s.stats.pulls - expected) < 0.0015
    assert abs(np.mean(s.stats.five_pities) - pr.expected_pulls_5star(pr.hazard_community(RATES))) < 0.6


def test_fifty_fifty_and_guarantee():
    s = sim(seed=3)
    s.pull(100_000)
    fives = [i for i in s.stats.history if i.rarity == 5]
    for a, b in zip(fives, fives[1:]):
        if a.result == "lost":
            assert b.result == "guaranteed" and b.featured
    wr = s.stats.wins / (s.stats.wins + s.stats.losses)
    assert 0.46 < wr < 0.54


def test_weapon_banner_always_featured_and_start_state():
    w = sim(weapon=True)
    w.pull(5000)
    assert all(i.featured for i in w.stats.history if i.rarity == 5)
    g = sim(pity5=79, guaranteed=True)
    first = g.pull_one()
    assert first.rarity == 5 and first.featured and first.result == "guaranteed"
    assert g.astrite == 160
