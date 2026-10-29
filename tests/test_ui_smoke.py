"""Headless smoke test: build the whole main window, visit every tab and sub-tab, render the share image."""
import os
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WUWA_NO_AUDIO", "1")


def test_main_window_all_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from wuwa_tracker.core.models import Pull
    from wuwa_tracker.core.storage import Storage
    from wuwa_tracker.ui.main_window import MainWindow
    from wuwa_tracker.ui.state import AppState

    st = Storage(tmp_path / "WuwaTracker" / "pulls.db")
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    pulls = []
    for i in range(150):
        q = 5 if i in (60, 140) else (4 if i % 10 == 9 else 3)
        name = {60: "Hsin", 140: "Verina"}.get(i, "Lumi" if q == 4 else "Sword of Night")
        pulls.append(Pull(1, 1000 + i % 3, q, name, t0 + timedelta(hours=i), 1, "1"))
    st.add_pulls(pulls)
    for k, v in {"player": "1", "prydwen_enabled": False, "auto_import": False, "update_check": False,
                 "weekly_summary": False, "gamedata_autocheck": False, "tray": False,
                 "v11_setup": True}.items():
        st.set_setting(k, v)
    st.add_income("2026-10-01", 500, player_id="1")
    state = AppState(st)
    w = MainWindow(state)
    w.show()
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i)
        app.processEvents()
    planner = w.page(3)
    for j in range(planner.sub.count()):
        planner.sub.setCurrentIndex(j)
        app.processEvents()
    planner.plan.astrite.setValue(16000)
    assert "%" in planner.plan.big.text()
    planner.whatif.preset("won")
    assert planner.whatif.rows["Difference"].v.text() != "–"
    sim = w.page(7)
    sim.anim.setChecked(False)
    sim.convene(10)
    from wuwa_tracker.ui.share_card import render
    img = render(state)
    assert img.width() == 1200
    st.backup("t")
    w.quit_app()
