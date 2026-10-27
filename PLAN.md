# WuWa Pull Tracker: Plan of Approach

A Windows desktop app that tracks Wuthering Waves Convene (gacha) history the way
wuwatracker.com does. It runs fully offline, adds a probability calculator, and
includes an AI assistant powered by a **local Ollama model**.

---

## 1. Goals

| # | Goal | Done when |
|---|------|-----------|
| G1 | Import pull history | A wuwatracker JSON export imports without duplicates. Re-importing a newer export only adds the new pulls. |
| G2 | Match wuwatracker's numbers | Pity, 4★ pity, total pulls, 5★ count and 50/50 win rate per banner equal the website's figures (test: Featured Resonator = 59/80, 2/10, 1,311 pulls, 23 × 5★, 46.67 % 50/50). |
| G3 | Probability calculator | Answers "with X pulls from my current pity/guarantee, what is the chance of N copies of the featured 5★?" plus expected pulls and Astrite. |
| G4 | Ollama assistant | Chat with a local model that can *look up* your stats and *call* the probability engine. The LLM never does the maths itself. |
| G5 | Windows-native | Double-click `run.bat`, or build a single `.exe` with PyInstaller. |

## 2. Tech choices (and why)

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.11+ | Matches the Data Science/AI curriculum. pandas/numpy-style thinking. |
| GUI | PySide6 (Qt 6) | Native-looking Windows app, dark theme, threads for non-blocking AI calls. |
| Charts | matplotlib (QtAgg backend) | Well known, easy to extend. |
| Storage | SQLite (`%APPDATA%\WuwaTracker\pulls.db`) | One file, SQL-queryable, no server. |
| AI | Ollama REST API (`http://localhost:11434`) | Local, private, free. Uses `/api/tags` and `/api/chat` with **tool calling**. |
| Packaging | PyInstaller → `WuwaTracker.exe` | Single-folder build, no Python needed on target PC. |

## 3. Architecture

```
wuwa_tracker/
├── core/                 ← pure Python, no GUI: unit-testable
│   ├── models.py         Pull dataclass, banner (cardPoolType) names, standard-5★ lists
│   ├── storage.py        SQLite schema, JSON import, de-duplication
│   ├── analysis.py       pity counters, 5★ history, 50/50 classification, luck stats
│   ├── probability.py    pity hazard models + dynamic-programming engine
│   ├── game_import.py    (experimental) read gacha URL from game log → fetch via API
│   └── ollama_client.py  model list, chat loop with tool calling, fallback mode
├── ui/
│   ├── main_window.py    tabs + dark theme
│   ├── overview_tab.py   banner cards (like the wuwatracker left column) + 5★ list
│   ├── history_tab.py    searchable/filterable pull table
│   ├── calculator_tab.py probability calculator + charts
│   ├── assistant_tab.py  Ollama chat
│   └── settings_tab.py   Ollama host/model, game path, pity model choice
└── app.py                entry point
tests/                    pytest: numbers must match wuwatracker
```

**Data flow:** JSON / game API → `storage` (SQLite) → `analysis` (stats per banner)
→ UI + `probability` → Ollama tools read the same `analysis`/`probability` functions.

## 4. Data model

The wuwatracker export (`version 0.0.2`) has one record per pull:
`cardPoolType, resourceId, qualityLevel (3/4/5), name, time, group`.

* **Ordering:** sort by `(time, group)`. Pulls inside one 10-pull share the same
  timestamp; `group` (1–10) gives the order within it.
* **Dedup key:** `(cardPoolType, time, group, resourceId)`.
* **Banner types seen in your file:** 1 Featured Resonator, 2 Featured Weapon,
  3 Standard Resonator, 4 Standard Weapon, 5 Beginner, 6 Beginner's Choice,
  8/10/11 (newer event/selector banners; names are editable in settings),
  12 Reverb Resonator Convene.
* **50/50 detection:** on the Featured Resonator banner, a standard 5★
  (Calcharo, Encore, Jianxin, Lingyang, Verina; the list is editable) is a **loss**.
  The next 5★ after a loss is **guaranteed** and doesn't count as a 50/50.

## 5. Probability engine

Kuro publishes the base rate (0.8 % for 5★), the 4★ rate (6 %), soft pity
(from around pull 66) and hard pity (80). It **does not** publish the per-pull curve
after 66, so the app offers three models:

1. **Community model (default):** 0.8 % until pull 65, then +4 %/pull (66–70),
   +8 %/pull (71–75), +10 %/pull (76–79), 100 % at 80. Editable in code.
2. **Flat:** 0.8 % until 79, 100 % at 80. This is the pessimistic lower bound.
3. **Fitted from your own pulls:** a Kaplan-Meier-style hazard estimate,
   `h(n) = #5★ at pity n / #pulls that reached pity n`, smoothed and blended with the
   community model where data is thin. This is the data-science part.

**Dynamic programming:** the state is `(pity, guaranteed?, copies obtained)`.
For each pull, the engine moves the probability mass to the next state:

* 5★ happens with probability `h(pity+1)`.
  * Character banner: if guaranteed → featured; else 50 % featured, 50 % lost and guaranteed.
  * Weapon banner: featured 100 %.
* Outputs: P(≥ k featured within N pulls), the full distribution curve, expected
  pulls to the next featured, the 50th/90th percentile of pulls needed, and
  Astrite (160 per pull).

The DP is exact. There's no Monte Carlo noise, and it runs in milliseconds.

## 6. Ollama integration

* Settings let you choose the host and model. The model list comes from `/api/tags`.
* **Tool calling** (llama3.1, qwen2.5, mistral-nemo and similar). The app exposes:
  * `get_banner_stats(banner)`: pity, guarantee, 5★ history
  * `featured_probability(banner, pulls, copies)`: the DP engine
  * `pulls_needed(banner, copies, confidence)`: inverse query
  * `list_five_stars(banner)`
* **Fallback** for models without tool support: a compact JSON summary of all
  banners is injected into the system prompt instead.
* Calls run in a background `QThread`, so the UI never freezes.

## 7. Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | Plan + data analysis of the export | ✅ |
| 2 | Core: import, storage, analysis, probability + tests | ✅ v0.1 |
| 3 | GUI: overview, history, calculator | ✅ v0.1 |
| 4 | Ollama assistant with tools | ✅ v0.1 |
| 5 | Direct game import (log URL → API) | ✅ v0.5.1 (scrambled log, Steam libraries); confirm on your PC |
| 6 | Packaging (`build_exe.bat`), icon, installer | ✅ script, run on Windows |
| 7 | Patch-proof game data layer (data file, auto-detect, online update, `tools/new_patch.py`) | ✅ v0.2 |
| 8 | Portraits, Prydwen tab, Convene Simulator + animation/sounds, Codes tab, owned-outside-pulls | ✅ v0.3–v0.5 |
| 9 | Roadmap 0.6 → 1.0 (section 8) | 📋 planned |

## 8. Roadmap (0.6 → 1.0)

Every idea from the brainstorm of 2026-10-27, grouped into releases. Effort: **S** = a few hours,
**M** = about a day, **L** = several days. Each release: tests first → build → screenshot check →
CHANGELOG → commit → push → GitHub release.

Already done from the old backlog: banner timeline (v0.2), portraits by `resourceId` (v0.3),
luck percentile (v0.1), reset timers in the header (v0.4.1).

### 0.6: reliability and data safety
| # | Item | Effort | Notes |
|---|------|--------|-------|
| 0.6.1 | Push v0.5.x to GitHub, confirm game import on the real PC | S | Blocks everything else that builds on the import |
| 0.6.2 | **Automatic backups**: dated copy of `pulls.db` before every import (keep last 20), ☰ → Restore backup | S | `core/backup.py` |
| 0.6.3 | **Export**: wuwatracker-compatible JSON (`version 0.0.2`), CSV and Excel (`openpyxl`) | S | Round-trip test: export → import gives identical DB |
| 0.6.4 | **Import check**: after each import, flag gaps (days with no pulls between pulls, banner suddenly empty, count mismatch vs. a wuwatracker export) | S | Shown in the import summary dialog |
| 0.6.5 | **Update check** through GitHub Releases API (on start, max once a day) | S | "Update available → open release page" |
| 0.6.6 | **Prydwen layout check**: weekly GitHub Actions job that fetches the live pages and runs the parsers | S | Warns before the tab breaks |

### 0.7: auto-import, tray and accounts
| # | Item | Effort | Notes |
|---|------|--------|-------|
| 0.7.1 | **Auto-import**: background watcher on `Client.log` (poll size/mtime every few seconds); a new history link triggers an import within seconds | M | Reuses `game_import`; toggle in Settings |
| 0.7.2 | **Tray icon**: daily/weekly reset countdown, "minimise to tray", quick actions (import, open) | M | `QSystemTrayIcon` |
| 0.7.3 | **Notifications**: new redemption codes, banner ends in 2 days, new pulls imported | S | Tray balloons; each type can be switched off |
| 0.7.4 | **Multiple accounts**: account switcher keyed by `playerId` in the header pill; all tabs filter by account | M | DB already stores `player_id`; add `accounts` table + migration |
| 0.7.5 | **Optional cloud sync**: put `pulls.db` + settings in a chosen folder (e.g. OneDrive) with a lock file | S | Simple "data folder" setting, no own server |

### 0.8: planner and statistics
| # | Item | Effort | Notes |
|---|------|--------|-------|
| 0.8.1 | **Income tracker**: log Astrite/Lunite/Tides per day or per patch (manual + quick-add presets: dailies, Tower, Abyss, events, patch rewards) | M | New table `income`; chart of income per patch |
| 0.8.2 | **Astrite planner**: current Astrite + Tides + expected income until a target date → pulls available → P(featured) on that date | M/L | Uses the DP engine; income rate from 0.8.1 or a manual estimate |
| 0.8.3 | **Wishlist / "should I pull?"**: upcoming banners with priorities ("Lynae S1, weapon optional"); P(all), P(each), and which item to drop if short | L | DP over a sequence of banners carrying pity/guarantee between them |
| 0.8.4 | **"What if" mode**: replay history with a lost 50/50 flipped, or a different pity model | S | |
| 0.8.5 | **Luck in context**: χ² / KS test of your pity distribution vs. the model, with a plain-language verdict | S/M | `scipy` optional; fallback implementation in numpy |
| 0.8.6 | **Bayesian soft-pity fit**: prior on the curve, update with your pulls, show credible intervals on the Probability tab | M | Extends the existing Beta-smoothed fit |

### 0.9: collection, banners and calendar
| # | Item | Effort | Notes |
|---|------|--------|-------|
| 0.9.1 | **Collection page**: grid of all resonators and weapons (owned in colour, rest greyed), sequence/refine level, filters by element/weapon type/rarity | M | Data: Prydwen character list + pulls + owned-outside-pulls |
| 0.9.2 | **Banner history + rerun tracker**: past banners per patch, "last ran X days ago", average rerun gap | M | Extend `game_data.json` with past phases |
| 0.9.3 | **Event calendar**: current events with end dates next to the reset timers | M | Source to decide (Prydwen / manual in game data) |
| 0.9.4 | **Tier list over time**: snapshot the tier list on every load, show rank changes per character | S | Stored in the Prydwen cache folder |

### 1.0: AI, polish and distribution
| # | Item | Effort | Notes |
|---|------|--------|-------|
| 1.0.1 | **Weekly AI summary** (pull-log narrator) shown on start-up | S | Ollama; plain template if Ollama is off |
| 1.0.2 | **Pull advice**: assistant tools for the planner and wishlist ("Lynae or save?") | M | New tools `plan_astrite`, `wishlist_odds` |
| 1.0.3 | **RAG over game info**: local notes + cached Prydwen guides retrieved into the chat | M | Simple keyword/embedding search via Ollama embeddings |
| 1.0.4 | **Persona presets**: analyst / hype friend | S | System-prompt variants |
| 1.0.5 | **Model benchmark**: same probability questions to several Ollama models, score tool use and correctness | M | Good school-project material |
| 1.0.6 | **Dutch/English UI** and a **light theme** | M | Qt translations (`.ts`), theme tokens in `theme.py` |
| 1.0.7 | **Shareable summary card**: PNG of banner stats + portraits | S/M | Rendered with QPainter |
| 1.0.8 | **Simulator extras**: weapon banner in the animation, achievements, session leaderboard | S/M | |
| 1.0.9 | **Ready-made .exe in GitHub Releases** built by GitHub Actions (windows-latest + PyInstaller) | M | No Python needed to install |
| 1.0.10 | **Refactor**: split `main_window.py` (header, menu actions, import flow, workers) | M | Do early in 1.0 so later items land cleanly |

### Open questions
- Does the v0.5.1 game import work on the real PC? If not, fixing it comes before 0.6.
- Is the app only for personal use, or should others install it easily? If the latter, move 1.0.9 forward.
- Event calendar source (0.9.3): Prydwen, or maintained by hand in `game_data.json`.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Soft-pity curve is unofficial | Model choice in settings; fitted model from your own data; flat model as lower bound. |
| Game API/log format changes | Game import is isolated in one module; JSON import always works. |
| Small local LLMs make up numbers | Tools force them to use the engine; the system prompt says "never compute odds yourself". |
| Unknown banner type IDs | Names are editable; unknown types still get pity tracking. |
| Game ToS | Only reads your own log/history URL (same as wuwatracker); no memory reading or injection. |
