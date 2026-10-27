"""Import-from-game: log decoding, link parsing, install discovery, time zone detection, full import (mocked API)."""
from datetime import datetime, timedelta, timezone

import pytest

from wuwa_tracker.core import game_import as gi
from wuwa_tracker.core.models import Pull

URL = ("https://aki-gm-resources-oversea.aki-game.net/aki/gacha/index.html#/record?svr_id=76402e5b20be2c39f095a152090afddc"
       "&player_id=606829202&lang=en&gacha_id=100001&gacha_type=6&svr_area=global&record_id=abc123"
       "&resources_id=917dfa695d6c6634ee4e972bb9168f6a&platform=PC")


def encode_client_log(plain: bytes) -> bytes:
    """Inverse of gi.decode_client_log, to build realistic scrambled logs."""
    inv = {}
    for b in range(256):
        d = (b ^ 0xA5) if (b & 0x0F) % 2 == 1 else (b ^ 0xEF)
        inv.setdefault(d, b)
    return bytes(inv[x] for x in plain)


def test_xor_scheme_is_a_bijection_for_text():
    plain = ("[2026.10.27-10.12.01] LogKuro: open " + URL + "\n").encode()
    assert gi.decode_client_log(encode_client_log(plain)) == plain


def test_finds_last_link_in_scrambled_and_plain_logs(tmp_path):
    old = URL.replace("abc123", "old")
    log = f"noise {old}\nmore noise\n\"url\":\"{URL}\"\n".encode()
    assert gi.find_url_in_bytes(encode_client_log(log)) == URL          # scrambled (new game versions)
    assert gi.find_url_in_bytes(log) == URL                             # plain (older versions / debug.log)
    assert gi.find_url_in_bytes(b"nothing here") is None


def test_find_gacha_url_with_game_folder(tmp_path):
    game = tmp_path / "Wuthering Waves"
    f = game / "Wuthering Waves Game" / gi.CLIENT_LOG
    f.parent.mkdir(parents=True)
    f.write_bytes(encode_client_log(f"x {URL} y".encode()))
    res = gi.find_gacha_url(str(game))                  # launcher folder given; game folder is one level deeper
    assert res.url == URL and res.source == f


def test_parse_link_and_endpoints():
    p = gi.parse_gacha_url(URL)
    assert p["playerId"] == "606829202" and p["cardPoolId"] == "917dfa695d6c6634ee4e972bb9168f6a"
    assert p["api"] == gi.API_GLOBAL and p["headers"]["Origin"].endswith("aki-game.net")
    cn = URL.replace("-oversea", "").replace(".net/", ".com/")
    assert gi.parse_gacha_url(cn)["api"] == gi.API_CN == "https://gmserver-api.aki-game2.com/gacha/record/query"
    with pytest.raises(gi.ImportError_):
        gi.parse_gacha_url("https://aki-gm-resources-oversea.aki-game.net/aki/gacha/index.html#/record?lang=en")


def test_steam_library_vdf():
    vdf = '"libraryfolders"\n{\n "0"\n {\n  "path"\t\t"C:\\\\Program Files (x86)\\\\Steam"\n }\n "1"\n {\n  "path"\t\t"D:\\\\Platforms\\\\Steam"\n }\n}'
    libs = [str(p) for p in gi.steam_libraries_from_vdf(vdf)]
    assert libs[1].replace("/", "\\") == "D:\\Platforms\\Steam"


def _api_records():
    # newest first, server-local time (Asia, UTC+8); one 2-pull at the same timestamp
    return {1: [{"resourceId": 1311, "qualityLevel": 5, "name": "Hsin", "time": "2026-10-27 18:00:00"},
                {"resourceId": 21010013, "qualityLevel": 3, "name": "Broadblade of Night", "time": "2026-10-27 18:00:00"},
                {"resourceId": 1203, "qualityLevel": 4, "name": "Old", "time": "2026-10-26 18:52:48"}]}


def test_full_import_detects_timezone_and_skips_known(monkeypatch):
    recs = _api_records()

    def fake_fetch(params, pt, timeout=15):
        if pt in recs:
            return recs[pt]
        return []
    monkeypatch.setattr(gi, "fetch_pool", fake_fetch)
    # already stored (from a wuwatracker export, in UTC): the 'Old' pull
    known = [Pull(1, 1203, 4, "Old", datetime(2026, 10, 26, 10, 52, 48, tzinfo=timezone.utc), 1, "606829202")]
    res = gi.import_from_game(URL, utc_offset_h=1, existing_pulls=known, log=lambda s: None)   # wrong region on purpose
    assert res.offset == 8                                    # auto-detected Asia server
    assert [p.name for p in res.pulls] == ["Hsin", "Broadblade of Night"]
    assert res.pulls[0].time == datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
    assert {p.group for p in res.pulls} == {1, 2}


def test_expired_link_gives_clear_error(monkeypatch):
    def fail(params, pt, timeout=15):
        raise RuntimeError("record id expired")
    monkeypatch.setattr(gi, "fetch_pool", fail)
    with pytest.raises(gi.ImportError_, match="expired"):
        gi.import_from_game(URL, 8, [], log=lambda s: None)
