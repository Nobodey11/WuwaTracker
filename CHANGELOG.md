# Changelog

## 1.1.1 (2026-10-29): release build fixed
- The GitHub release build (Windows .exe) and the test check failed after all tests had passed; fixed, so the
  1.1 features now come with a downloadable WuwaTracker-1.1.1-windows.zip.
- Running the tests no longer turns on "start with Windows" on the PC that runs them.

## 1.1.0 (2026-10-29): starts with Windows, syncs while you play
- **Start with Windows** (Settings → Automation, per user, no admin rights): the tracker starts quietly in the tray
  (`--tray`), and only the light parts of the app are loaded until you open the window. Turned on once
  automatically on the first start of 1.1, together with auto-import.
- **Game detection**: the tracker notices when Wuthering Waves starts and stops (it reads only the list of running
  program names, like Task Manager; the game itself is never touched). The game's program names can be changed.
- **Syncs while you play**: during the game the log is checked every 2 seconds. Every time you open
  Convene → History (also again with the same link) your new pulls are imported, debounced to one import when you open
  and close it quickly, with up to 2 retries when the link isn't active yet. The notification names your new 5★s and
  the 50/50 result. Open pages refresh by themselves.
- **Pull overlay** during the game: a small always-on-top card with pity, guarantee and the featured-5★ chance for the
  next pull and the next 10, for the character and weapon banner. Drag to move; × hides it. Shows over borderless /
  windowed mode, not exclusive full screen.
- **Sync reminders**: after 20 minutes of play without a sync, and when the game closes without one.
- **Session summary** when the game closes (new pulls, 5★s, play time); optional **close the tracker with the game**;
  optional **open the window when the game starts**.
- **One copy only**: starting the tracker again brings the running window to the front.
- **Steam launch option** to copy from Settings, as an alternative to starting with Windows.
- Status chip in the header and tray: "Waiting for Wuthering Waves" / "Game running · auto-import on".
- Tests: 66 (game detection, start-with-Windows registry, re-opened history with the same link, import retries,
  the session controller).

## 1.0.0 (2026-10-27): the whole roadmap (0.6 → 1.0)
Everything from the 0.6–1.0 roadmap in PLAN.md, shipped together.

**Reliability (0.6)**
- **Automatic backups** of your database before every import, restore and delete (last 20 kept); ☰ → Backups (Ctrl+B)
  to make one or restore one (a restore is itself undoable).
- **Export** to wuwatracker JSON (round-trips exactly), CSV and **Excel** (pulls with pity, banner summary, 5★ history;
  Ctrl+E). run.bat installs the new `openpyxl` dependency automatically.
- **Import checks**: after a game import the app warns when the new records don't connect to your stored history (a
  possible gap) or a 10-pull is incomplete. ☰ → Compare with a wuwatracker export shows per banner what's missing.
- **Update check** against GitHub Releases (once a day, can be turned off); a chip in the header links to the release.
- **Prydwen layout check**: a weekly GitHub Actions job (`tools/prydwen_check.py`) tests every parser against the live
  pages, so a Prydwen redesign is noticed before the app breaks.

**Automatic (0.7)**
- **Auto-import**: the app watches the game log and imports new pulls a few seconds after you open Convene → History
  (only the new part of the log is read; turn it on in Settings → Automation).
- **Tray icon** with daily/weekly reset countdowns and quick import; optionally keep running in the tray when closed.
- **Notifications** for new redemption codes, banners/events ending within 2 days (also a ⏳ chip in the header) and
  auto-imported pulls (with the 5★ names).
- **Accounts**: give each player id a name (☰ → Rename this account); the account pill shows it.
- **Data folder** can live anywhere (e.g. OneDrive) to sync between PCs, with a lock that warns when another PC is using it.

**Planning & statistics (0.8): new Planner tab**
- **Astrite planner**: Astrite + Tides now, income per day and a target date (or jump to a banner date) → pulls on that
  date, chance of the featured 5★ from your real pity/guarantee, the date you reach 90 %, and a chance-by-date chart.
- **Wishlist / "should I pull?"**: several wishes in priority order (e.g. Lynae S1 + her weapon) with one budget; exact
  chance per wish and for everything, and which wish to drop. Radiant Tides only pay for characters, Forging Tides only
  for weapons. Verified against a Monte Carlo simulation in the tests.
- **Income log** (quick +60 / +90 / +300 buttons, monthly chart); after 7 logged days the planner uses your real income,
  before that an editable estimate.
- **What if**: replay your 50/50s with any outcome changed (or all won / all lost / coin flips), and compare your pulls
  with an average player's for the same copies.
- **Luck test**: KS and chi-square tests of your pity distribution against the model (simulated p-values) with a plain
  verdict, plus a **Bayesian fit** of the soft-pity curve with a 90 % credible band and intervals for the 5★ rate and
  P(featured in 80 pulls).

**Collection & calendar (0.9)**
- **Collection tab**: every resonator and weapon (Prydwen lists), owned in colour with S0–S6 / R1–R5, filters by
  rarity, element/weapon type, owned and limited.
  Click any card (or ＋ Add manually) to add copies you own without pulling; the **Rover** (every attunement) is always
  owned, and adding copies to a Rover sets its sequence.
- **Calendar tab**: current and upcoming banners from Prydwen's banner page (exact times for your server region),
  game-data banners and events, your own events, and daily/weekly/monthly resets, with live countdowns.
- **Rerun tracker**: every known run of each limited 5★ (game data, Prydwen, remembered over time, and your own pulls),
  sorted by the longest wait.
- **Tier history**: the tier list is snapshotted whenever it changes; the character panel shows each character's
  rating over time.

**Polish (1.0)**
- **Weekly summary** on the first start of a week (☰ → Weekly summary, Ctrl+W); optional "Let the AI tell it" that only
  rephrases the app's facts.
- **AI assistant**: new tools `plan_astrite`, `wishlist_odds` and `search_notes` (local search over your own notes,
  cached Prydwen guides and the banner calendar); **personas** (analyst, hype friend, saving coach);
  **Benchmark models…** scores your Ollama models on questions about your own data (also `tools/benchmark.py`).
- **Light theme** and a **Dutch** interface option (Settings → Appearance; navigation, menus and the new pages are
  translated, older pages still partly English).
- **Share image** (☰ → Save share image…): a 1200×675 PNG with your banner stats and latest 5★ portraits.
- **Simulator**: 11 achievements, a top-10 leaderboard (fewest pulls per featured 5★) and a weapon-style reveal frame.
- **Ready-made .exe**: pushing a `v*` tag builds `WuwaTracker-<version>-windows.zip` on GitHub Actions and attaches it
  to the release, so no Python is needed.
- Refactor: the main window is split into `header.py`, `import_flow.py`, `background.py`, `tray.py` and `dialogs.py`.
- Tests: 60 (new: backups, exports, import checks, log watcher, planner, wishlist vs. Monte Carlo, what-if, luck tests,
  Prydwen banners/weapons, calendar, reruns, collection, summary, RAG, benchmark scoring, achievements, data folder,
  and a headless test that opens every tab).

## 0.5.1 (2026-10-27): import from game fixed
- **Scrambled Client.log**: newer game versions XOR-encode the log, so the history link was never found. The log is
  now decoded first (the raw text and the KRSDK debug.log are still tried too).
- **Finds the install anywhere**: game folder from Settings, Windows registry traces (MUI cache, firewall rules,
  uninstall entries), *every* Steam library listed in Steam's libraryfolders.vdf (e.g. D:\Platforms\Steam) and common
  folders on all drives; both the launcher folder and the "Wuthering Waves Game" subfolder are checked.
- **API fixes**: browser-style headers (Origin/Referer/User-Agent) like working exporters, correct CN endpoint
  (gmserver-api.aki-game2.com), and a clear message when the link has expired instead of silently importing 0 pulls.
- **No duplicates, right times**: the server time zone is auto-detected by matching the downloaded records with pulls
  you already have, and already-known pulls are skipped by banner + time + item.
- Runs in the background; if no link is found you can pick your game folder (remembered) or paste the link; a summary
  shows how many new pulls were added per banner.

## 0.5.0 (2026-10-26): redemption codes + characters owned outside pulls
- New **Codes** tab: active redemption codes from Prydwen.gg with reward icons, a Copy button and a "Redeemed" tick-off
  (remembered). The tab shows a 🎁 badge with the number of codes you still have to redeem, and the status bar announces
  newly added codes. Expired codes are listed on demand. Refreshed every 3 hours (↻ for now).
- **Owned outside pulls**: characters/weapons you got for free (event gifts, free units) count as owned in the Prydwen
  tab (badges, "Only mine"), the character panel and the AI assistant. Add them with "＋ I own this" in the character
  panel or via ☰ → Owned outside pulls. Stored in the app and mirrored to a local, git-ignored my_characters.json.
- AI assistant tool `redemption_codes`.

## 0.4.4 (2026-10-26): manual reveals + new sound design
- Reveals no longer advance by themselves: each item waits for a click or key press ("Click to continue ▶").
  Clicking during a reveal finishes it instantly; Skip/Esc still jumps to the results.
- Sound effects redesigned in a cinematic style inspired by the game's Convene (still fully original/synthesised):
  stereo, long hall reverb, deep sub-bass swells and drops, airy wind risers, glassy crystal chimes and choir-like pads.
  A 5★ gets a gold cascade, a big choir chord and sparkles. Sounds are generated in the background on first start.

## 0.4.3 (2026-10-26): all items in the animation + sound effects
- The Convene animation now reveals every item in pull order, including blue 3★ weapons (shown at double speed,
  so a 10-pull stays snappy).
- Original sound effects, synthesised in code (no game audio): a rising whoosh, a shimmer when the comet turns gold,
  a burst impact per rarity, reveal chimes for 3★/4★/5★ and a rising tick for each star.
  Toggle and volume slider in the simulator panel; settings are remembered.
- Long item names shrink to fit beside the portrait.

## 0.4.2 (2026-10-26): Convene animation
- Convene Simulator plays a full-window pull animation (original artwork, not game footage): starry sky,
  comet streak whose colour shows the best result (late gold upgrade for a 5★), a flash and shockwave burst, then a
  reveal per 4★/5★ with light rays, sliding portrait, stars popping in, a shine sweep and the 50/50 result.
  Click to advance, Skip/Esc to jump to the results; can be turned off ("Play convene animation").
- The Standard Resonator banner card shows a standard-pool 5★ portrait (changes daily) until you pull a 5★ there.

## 0.4.1 (2026-10-26): app icon + cleaner header
- New app icon (gold sparkle inside a gold-to-purple "pity ring"), used for the window, the Windows taskbar and
  the .exe built with build_exe.bat.
- Cleaner top area: one navigation bar (icon, wordmark, tabs, player, ☰ menu) and a thin status strip
  (patch/data version, daily and weekly reset). The old menu bar moved into the ☰ menu; shortcuts still work
  (Ctrl+O import, Ctrl+G game import, F5 update check, Ctrl+Q exit).

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
