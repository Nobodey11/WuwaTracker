"""Run: python -m pytest tests  (set WUWA_SAMPLE to your export to run the wuwatracker-match tests)."""
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from wuwa_tracker.core import probability as pr
from wuwa_tracker.core.analysis import all_stats, banner_stats
from wuwa_tracker.core.models import Pull
from wuwa_tracker.core.storage import Storage, read_wuwatracker_json

SAMPLE = os.environ.get("WUWA_SAMPLE")


def mk(pool, names_q):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Pull(pool, i, q, n, t0 + timedelta(minutes=i)) for i, (n, q) in enumerate(names_q)]


def test_pity_and_5050():
    seq = [("x", 3)] * 9 + [("Lingyang", 5)] + [("y", 4)] + [("x", 3)] * 4 + [("Hsin", 5)] + [("Iuno", 5)] + [("x", 3)] * 3
    s = banner_stats(1, mk(1, seq))
    assert [f.result for f in s.five_stars] == ["lost", "guaranteed", "won"]
    assert [f.pity for f in s.five_stars] == [10, 6, 1]
    assert s.pity5 == 3 and s.pity4 == 3
    assert s.wins == 1 and s.losses == 1 and not s.guaranteed


def test_hazard_models_valid():
    for f in (pr.hazard_community, pr.hazard_flat):
        h = f()
        assert h[80] == 1.0 and np.all((h[1:] >= 0) & (h[1:] <= 1))
        assert abs(pr.pity_pmf(h).sum() - 1) < 1e-9


def test_weapon_banner_is_guaranteed_at_80():
    h = pr.hazard_community()
    assert pr.featured_distribution(h, 80, 1, featured_chance=1.0).probability == pytest.approx(1.0)
    assert pr.featured_distribution(h, 79, 1, pity=1, featured_chance=1.0).probability == pytest.approx(1.0)


def test_character_banner_160_hard_cap():
    h = pr.hazard_community()
    assert pr.featured_distribution(h, 160, 1).probability == pytest.approx(1.0)
    assert pr.featured_distribution(h, 80, 1, guaranteed=True).probability == pytest.approx(1.0)
    assert pr.featured_distribution(h, 80, 1).probability < 1.0


def test_dp_matches_monte_carlo():
    h = pr.hazard_community()
    rng = np.random.default_rng(1)
    N, pulls, hits = 40000, 120, 0
    for _ in range(N):
        pity, g, got = 30, False, 0
        for _ in range(pulls):
            pity += 1
            if rng.random() < h[pity]:
                pity = 0
                if g or rng.random() < 0.5:
                    got += 1; g = False
                else:
                    g = True
        hits += got >= 1
    exact = pr.featured_distribution(h, pulls, 1, pity=30).probability
    assert abs(hits / N - exact) < 0.01


def test_storage_dedup(tmp_path):
    st = Storage(tmp_path / "t.db")
    ps = mk(1, [("a", 3), ("b", 4)])
    assert st.add_pulls(ps) == 2
    assert st.add_pulls(ps) == 0


@pytest.mark.skipif(not SAMPLE, reason="set WUWA_SAMPLE=path/to/export.json")
def test_matches_wuwatracker_screenshot():
    pulls, _ = read_wuwatracker_json(SAMPLE)
    s = all_stats(pulls)
    fr = s[1]
    assert (fr.total_pulls, fr.pity5, fr.pity4, fr.count5, fr.count4) == (1311, 59, 2, 23, 154)
    assert fr.astrite == 209_760
    assert round(fr.win_rate * 100, 2) == 46.67
    assert round(fr.avg_featured_pity, 2) == 83.47
    assert round(fr.rate5 * 100, 2) == 1.75
    assert (s[2].pity5, s[2].pity4) == (58, 8)
    assert (s[12].pity5, s[12].pity4) == (10, 7)


def test_fitted_hazard_is_valid_and_flat_before_soft_pity():
    h = pr.hazard_fitted([70, 72, 7, 68, 74], [30])
    assert h[80] == 1.0 and np.all((h[1:] >= 0) & (h[1:] <= 1))
    assert len(set(np.round(h[1:66], 12))) == 1
    assert abs(pr.pity_pmf(h).sum() - 1) < 1e-9


def test_next_pulls():
    h = pr.hazard_community()
    o = pr.next_pulls(h, 0, False, 0.5, 0)
    assert abs(o[1]["any5"] - 0.008) < 1e-12 and abs(o[1]["featured"] - 0.004) < 1e-12
    assert o[10]["four_plus"] == 1.0                      # 4★ pity guarantee
    assert abs(o[10]["any5"] - (1 - 0.992 ** 10)) < 1e-12
    g = pr.next_pulls(h, 0, True, 0.5, 0)
    assert abs(g[10]["featured"] - g[10]["any5"]) < 1e-12  # guaranteed: any 5★ is featured
    assert pr.next_pulls(h, 79, False, 1.0, 3)[1]["featured"] == 1.0   # weapon at hard pity
    assert pr.next_pulls(h, 5, False, None)[1]["featured"] is None
