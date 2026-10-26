"""Prydwen parser tests on trimmed real page snapshots (tests/fixtures). No network needed."""
from pathlib import Path

from wuwa_tracker.core import prydwen as pw

FX = Path(__file__).parent / "fixtures"


def test_tier_list_parser():
    tl = pw.parse_tier_list((FX / "prydwen_tierlist.html").read_text(encoding="utf-8"))
    assert tl.tiers == ["T0", "T0.5"]
    names = [e.name for e in tl.entries]
    assert names[:2] == ["Hiyuki", "Hsin"] and "fake" not in "".join(names)
    by = tl.by_key()
    h = by[pw.key("Hsin")]
    assert (h.tier, h.role, h.element, h.rarity, h.sequence, h.mark) == ("T0", "DPS", "Electro", 5, "S0", "up")
    assert h.tags == ["Flare", "Unison", "Coord"]
    assert h.icon.endswith("hsin_icon.webp") and h.slug == "hsin"
    assert by[pw.key("Iuno")].role == "Hybrid" and by[pw.key("Chisa")].role == "Support"
    assert by[pw.key("Lynae")].mark == "down" and by[pw.key("Luuk Herssen")].slug == "luuk-herssen"
    assert by[pw.key("Aemeath")].tags[-1] == "Expert +1"


def test_character_parser():
    c = pw.parse_character((FX / "prydwen_character_hsin.html").read_text(encoding="utf-8"), "hsin")
    assert (c.name, c.element, c.updated) == ("Hsin", "Electro", "22/October/2026")
    assert c.card.endswith("hsin_card.webp")
    assert c.roles == [{"role": "DPS", "sequence": "S0", "ratings": {
        "Tower of Adversity": "T0", "Whimpering Wastes": "T0",
        "Tower of Adversity (Value)": "T0", "Whimpering Wastes (Value)": "T0"}}]
    assert [(w["name"], w["refine"], w["rarity"]) for w in c.weapons] == [("Blooming Jadehaven", 1, 5), ("Stringmaster", 5, 4)]
    assert c.echo_sets == [{"name": "Heart of Sworn Vigil",
                            "icon": "https://cdn.prydwen.gg/images/wuthering-waves/echo-sets/heart-of-sworn-vigil.webp"}]


def test_name_keys_match_game_names():
    assert pw.key("Yangyang: Xuanling") == pw.key("Yangyang Xuanling") == pw.key("yangyang-xuanling")


def test_cache_and_portraits(tmp_path, monkeypatch):
    p = pw.Prydwen(tmp_path)
    html = (FX / "prydwen_tierlist.html").read_bytes()
    calls = []
    monkeypatch.setattr(p, "_get", lambda url: calls.append(url) or html)
    tl = p.tier_list()
    p.tier_list()                       # second call served from cache
    assert len(calls) == 1 and len(tl.entries) == 11
    assert p.portrait_url("Hsin").endswith("hsin_icon.webp")
    assert p.portrait_url("Emerald of Genesis", 21020015).endswith("/weapons/21020015.webp")
    assert p.find_slug("Luuk Herssen") == "luuk-herssen"
    # offline: stale cache still works
    monkeypatch.setattr(p, "_get", lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert len(p.tier_list(force=True).entries) == 11


def test_ai_tool_prydwen_character(tmp_path, monkeypatch):
    from wuwa_tracker.core.ollama_client import ToolBox
    p = pw.Prydwen(tmp_path)
    pages = {pw.TIER_URL: (FX / "prydwen_tierlist.html").read_bytes(),
             pw.CHAR_URL.format(slug="hsin"): (FX / "prydwen_character_hsin.html").read_bytes()}
    monkeypatch.setattr(p, "_get", lambda url: pages[url])
    tb = ToolBox(lambda: {}, lambda: None, None, lambda: p, lambda: {"hsin": 2})
    r = tb.run("prydwen_character", {"name": "hsin"})
    assert r["tier_list_rating"] == "T0" and r["role"] == "DPS" and r["copies_owned_from_pulls"] == 2
    assert r["best_weapons"][0] == "Blooming Jadehaven (R1)" and r["echo_sets"] == ["Heart of Sworn Vigil"]
    assert "error" in tb.run("prydwen_character", {"name": "Nobody"})
