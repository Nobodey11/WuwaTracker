"""Owned-outside-pulls list and the codes AI tool."""
import json
from pathlib import Path

from wuwa_tracker.core import prydwen as pw
from wuwa_tracker.core.storage import Storage

FX = Path(__file__).parent / "fixtures"


def test_extras_count_as_owned(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("PySide6")
    from wuwa_tracker.ui import state as st
    local = tmp_path / "my_characters.json"
    local.write_text(json.dumps({"Rebecca": 1}))
    monkeypatch.setattr(st, "LOCAL_EXTRAS", local)
    s = st.AppState(Storage(tmp_path / "t.db"))
    assert s.extras() == {"Rebecca": 1}                         # merged from the local file
    assert s.owned()[pw.key("Rebecca")] == 1
    s.set_extra("Rebecca", 2)
    assert json.loads(local.read_text()) == {"Rebecca": 2}
    s.set_extra("Rebecca", 0)
    assert pw.key("Rebecca") not in s.owned()
    s2 = st.AppState(Storage(tmp_path / "t.db"))                # removal survives a restart
    assert s2.extras() == {}


def test_codes_tool(tmp_path, monkeypatch):
    from wuwa_tracker.core.ollama_client import ToolBox
    p = pw.Prydwen(tmp_path)
    monkeypatch.setattr(p, "_get", lambda url: (FX / "prydwen_codes.html").read_bytes())
    tb = ToolBox(lambda: {}, lambda: None, None, lambda: p)
    tb.redeemed = lambda: ["WUTHERINGGIFT"]
    r = tb.run("redemption_codes", {})
    assert r["active"][0]["code"] == "WUTHERINGGIFT" and r["active"][0]["redeemed_by_user"] is True
    assert "Astrite x50" in r["active"][0]["rewards"]
