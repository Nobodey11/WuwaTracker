# Keeping the tracker up to date each patch

Wuthering Waves gets a new version about every 6 weeks, with two banner phases per version.
Everything that changes between patches lives in **one data file**, so updating doesn't need code changes:

```
wuwa_tracker/data/game_data.json
```

| Section | What it holds | How often it changes |
|---|---|---|
| `banners` | Patch, phase, dates, featured 5★/4★ | **Every phase** |
| `limited_5star_*` / `standard_5star_*` | Which 5★ items count as a won or lost 50/50 | New characters every patch; the standard pool rarely |
| `banner_types` | `cardPoolType` id → name + kind (50/50 rules or not) | When Kuro adds a new convene type |
| `rates` | Base rates, soft-pity steps, hard pity, Astrite per pull | Rarely (only if new info appears) |
| `data_version` | `YYYY.MM.DD[.n]`, bumped automatically by the tool | Every change |

## How the app keeps itself current

1. **Automatic detection, no setup needed.** After every import the app compares your pulls with the game data.
   If a pull contains a 5★ or a banner type the data doesn't know, a dialog asks you to classify it
   (limited or standard, banner kind). Your answers go to `%APPDATA%\WuwaTracker\game_data.user.json`
   and override the data from then on.
2. **Out-of-date warning.** If no banner phase in the data covers today, the header shows **⚠** and the
   Tracker tab tells you the patch info is missing.
3. **Online update, optional.** Put `game_data.json` somewhere public (e.g. your GitHub repo) and paste the
   *raw* link in **Settings → Game data → Update URL**. On every start (or F5) the app downloads it, validates it,
   and uses it if its `data_version` is newer. Bad files are rejected, so a typo can't break the app.

Layers, from lowest to highest priority: bundled file → downloaded file (if newer) → your own overrides.

## Per-patch checklist (about 5 minutes)

Run these from the project folder (inside `.venv`):

```bat
:: 1. Export from wuwatracker (or use File → Import from game) and see what's new
python tools\new_patch.py scan C:\path\to\wuwatracker-pulls.json

:: 2. Add the new phase(s). The dates and banners are in the official livestream/patch notes.
python tools\new_patch.py phase --patch 3.8 --phase 1 --start 2026-11-11 --end 2026-12-02 ^
    --res "NewChar, Rerun1, Rerun2" --weap "NewWeapon, Weap1, Weap2" --four "A, B, C"

:: 3. Only if something unusual happened
python tools\new_patch.py classify "SomeChar" standard          &:: added to the standard pool
python tools\new_patch.py banner-type 13 "New Convene" event      &:: new convene type
python tools\new_patch.py rates --steps "66:0.04,71:0.08,76:0.10"  &:: new soft-pity info

:: 4. Validate + run the tests
python tools\new_patch.py check
python -m pytest tests

:: 5. Publish (if you use an update URL)
git add wuwa_tracker\data\game_data.json && git commit -m "Game data: patch 3.8" && git push
```

`tools/new_patch.py` bumps `data_version`, adds new featured 5★ to the limited lists, sets `game_patch`,
and refuses to save invalid data.

## Updating the app's code

If the project is a git clone, run `update.bat`. It pulls the latest code and data, updates the dependencies
and runs the tests.

## Ideas to automate it further
* A scheduled task (e.g. a GitHub Action or a Claude scheduled task) that checks the official patch notes each
  patch, opens a pull request with the new `phase`, and lets the tests validate it.
* Use the local Ollama model to read pasted patch notes and suggest the `phase` command.
