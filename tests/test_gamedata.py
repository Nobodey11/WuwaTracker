"""Game-data layer tests. The first test also guards every patch update of game_data.json."""
import json
from datetime import date

import numpy as np

from wuwa_tracker.core import probability as pr
from wuwa_tracker.core.analysis import all_stats
from wuwa_tracker.core.gamedata import BUNDLED, GameData, GameDataStore, validate
from tests.test_core import mk


def bundled():
    return json.loads(BUNDLED.read_text(encoding="utf-8"))


def test_bundled_game_data_is_valid():
    assert validate(bundled()) == []


def test_rates_drive_the_hazard():
    r = dict(bundled()["rates"], soft_pity_steps=[[60, 0.05]], hard_pity5=70)
    h = pr.hazard_community(r)
    assert len(h) == 71 and h[70] == 1.0 and h[59] == r["base5"] and abs(h[61] - (r["base5"] + 0.10)) < 1e-12
    assert pr.featured_distribution(h, 70, 1, featured_chance=1.0).probability > 0.999999


def test_layers_and_user_overrides(tmp_path):
    store = GameDataStore(tmp_path)
    gd = store.load()
    assert gd.source == "bundled"
    # new content from a "future patch"
    pulls = mk(1, [("x", 3)] * 5 + [("Brandnew", 5)]) + mk(13, [("y", 3)])
    items, pools = gd.find_unknown(pulls)
    assert items == [("Brandnew", False)] and pools == [13]
    store.classify("Brandnew", "standard")
    store.set_banner_type(13, "Shiny Convene", "featured_character")
    gd = store.load()
    assert gd.find_unknown(pulls) == ([], [])
    assert "Brandnew" in gd.standard_resonators and gd.has_5050(13) and gd.name(13) == "Shiny Convene"
    s = all_stats(pulls, gd)
    assert s[1].five_stars[0].result == "lost"
    # reclassify an existing standard character
    store.classify("Encore", "limited")
    assert "Encore" not in store.load().standard_resonators


def test_newer_remote_data_wins_and_invalid_is_ignored(tmp_path):
    store = GameDataStore(tmp_path)
    newer = bundled(); newer["data_version"] = "2099.01.01"; newer["game_patch"] = "9.9"
    store.remote_path.write_text(json.dumps(newer))
    assert store.load().patch == "9.9" and store.load().source == "downloaded"
    bad = dict(newer); bad["schema"] = 99
    store.remote_path.write_text(json.dumps(bad))
    assert store.load().source == "bundled"


def test_check_update_from_url(tmp_path):
    store = GameDataStore(tmp_path)
    newer = bundled(); newer["data_version"] = "2099.01.01"
    src = tmp_path / "remote.json"; src.write_text(json.dumps(newer))
    ok, msg = store.check_update(src.as_uri())
    assert ok and store.load().version == "2099.01.01"
    ok, msg = store.check_update(src.as_uri())
    assert not ok and "up to date" in msg


def test_schedule_lookup():
    gd = GameData(bundled())
    assert gd.patch_of(date(2026, 10, 18)) == "3.7 P1"
    assert gd.patch_of(date(2020, 1, 1)) is None


def test_new_patch_tool(tmp_path):
    from tools.new_patch import main
    f = tmp_path / "gd.json"; f.write_text(json.dumps(bundled()))
    main(["--file", str(f), "phase", "--patch", "3.8", "--phase", "1", "--start", "2026-11-11", "--end",
          "2026-12-02", "--res", "Futurechar, Hsin", "--weap", "Futureblade"])
    d = json.loads(f.read_text())
    assert d["game_patch"] == "3.8" and "Futurechar" in d["limited_5star_resonators"]
    assert d["limited_5star_resonators"].count("Hsin") == 1
    assert validate(d) == []
    main(["--file", str(f), "rates", "--steps", "65:0.05,72:0.1"])
    assert json.loads(f.read_text())["rates"]["soft_pity_steps"] == [[65, 0.05], [72, 0.1]]
