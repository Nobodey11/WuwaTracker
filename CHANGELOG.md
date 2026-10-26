# Changelog

## 0.4.0 (2026-10-26): portraits everywhere, Prydwen guides in-app, Convene Simulator
- **Pull History** shows a portrait next to every 4★/5★ (and weapons), loaded lazily for the visible rows only.
- **Prydwen tab** now has two sub-tabs:
  - *Tier list & my characters*: the native tier list + character panel (double-click a character = full guide).
  - *Prydwen website · guides*: Prydwen's real pages in a built-in browser (full character guides, and the
    Whimpering Wastes tier list via their own switch). Only prydwen.gg opens inside the app; other links go to
    your normal browser. Needs the optional `PySide6-WebEngine` package (run.bat installs it once, ~120 MB);
    without it guides open in your normal browser.
- **Convene Simulator** mini-game: free x1 / x10 pulls on the current banners with the real rules (soft pity,
  50/50 + guarantee, 4★ every 10, rate-up 4★s), animated reveal with portraits and gold/purple flashes, session stats
  and drop log; optionally start from your real pity. Engine verified against the probability model in tests.

## 0.3.2 (2026-10-26): disclaimer
- Added DISCLAIMER.md, a README notice and Help → About: based on the WuWa Tracker pull tracker, not affiliated with
  WuWa Tracker, Prydwen.gg or Kuro Games, strictly for personal use.

## 0.3.1 (2026-10-26): banner card art
- Banner cards on the Tracker tab show portrait art faded into the card (like wuwatracker):
  the current featured character for the Featured Resonator banner (from game data), otherwise your latest 5★
  on that banner (weapons by resourceId). Hover the art to see who it is.
- Prydwen character list (card art for every character) is cached alongside the tier list.

## 0.3.0 (2026-10-26): Prydwen tab + portraits
- New **Prydwen** tab: the prydwen.gg Wuthering Waves tier list (Tower of Adversity) by tier and role, with
  element, trend (▲ ▼ NEW), tags, search, "only mine" filter, and owned badges (S0–S6 / ×n from your pulls).
- Click a character to see the Prydwen ratings (ToA / Whimpering Wastes / value), best weapons (✓ if owned),
  echo sets and portrait, plus a button to open the full guide on prydwen.gg.
- Portraits on the Tracker tab's 5★ list (characters via the Prydwen tier list, weapons by game resourceId).
- Everything is fetched on demand and cached in %APPDATA%\WuwaTracker\prydwen (tier list 12 h, characters 3 days,
  images once); works offline from cache. Can be turned off in Settings.
- AI assistant tool `prydwen_character` (rating, role, best weapons, copies owned).
- Automatic game-data checks no longer show an error in the status bar when offline.

## 0.2.1 (2026-10-26): odds for the next 1 and next 10 pulls
- New "Your next pulls" card on the Tracker tab: chance of any 5★, the featured 5★ (50/50 or guarantee aware)
  and a 4★-or-better on the very next pull and within the next 10 pulls, for the selected banner.
- The same two rows on the Probability tab (they follow the pity/guarantee you enter).
- AI assistant tool `next_pulls`.

## 0.2.0 (2026-10-26): kept up to date per patch
- All patch-dependent knowledge moved to `wuwa_tracker/data/game_data.json` (banner types, standard/limited 5★,
  soft-pity rates, banner calendar). Nothing game-specific is hard-coded any more.
- Three data layers: bundled → downloaded from your update URL (if newer and valid) → your own overrides.
- New patch content (unknown 5★ or banner type) is detected after every import, and a dialog asks you to classify it.
- Out-of-date warning when no banner phase covers today.
- Help menu: check for game data updates (F5), classify new content, about game data.
- Banner schedule on the Tracker tab, a Patch column in Pull History, and the patch in the 5★ tooltips.
- AI assistant gets a `get_banner_schedule` tool.
- `tools/new_patch.py` for the per-patch routine (scan / phase / classify / banner-type / rates / check).
- `update.bat`, `docs/PATCH_UPDATE.md`, and tests for the data layer and the tool.
- Game data seeded with patch 3.7 (phase 1: Hsin; phase 2: Suoming).

## 0.1.0 (2026-10-26)
- First version: wuwatracker JSON import, SQLite storage, pity/50-50 stats, history table, exact
  probability calculator, Ollama assistant with tool calling, experimental game import.
