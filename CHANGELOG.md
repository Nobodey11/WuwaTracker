# Changelog

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
