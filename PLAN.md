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
| 5 | Direct game import (log URL → API) | 🧪 experimental, test on your PC |
| 6 | Packaging (`build_exe.bat`), icon, installer | ✅ script, run on Windows |
| 7 | Patch-proof game data layer (data file, auto-detect, online update, `tools/new_patch.py`) | ✅ v0.2 |
| 8 | Improvements (see below) | backlog |

## 8. Improvement ideas (backlog)

**Data & tracking**
1. **Auto-import from the game**: watch `Client.log` and pull new records whenever you open the in-game Convene history (the same way wuwatracker's PowerShell script works).
2. **Banner timeline**: link each pull to the actual banner/patch (e.g. "3.1 phase 2: Hsin") using a small banner calendar JSON, so the stats can be grouped per patch.
3. **Character & weapon icons**: cache icons by `resourceId` for the 5★ portrait grid.
4. **Export**: CSV/Excel for analysis in pandas, plus a wuwatracker-compatible JSON export so the data stays portable.
5. **Multiple accounts** (keyed by `playerId`).

**Probability & statistics**
6. **Astrite planner**: enter your current Astrite, Radiant Tides, daily income (Lunite, events, etc.) and a target banner date. The app shows the probability of reaching the target *on that date*.
7. **Luck percentile**: compare your average pity with the theoretical distribution, the way wuwatracker's "Bottom 37.59 %" does, but computed from the model instead of other users.
8. **Hypothesis test**: χ²/KS test of your observed pity distribution against the community model. Is your luck statistically unusual? (Good school-project material.)
9. **Bayesian rate fitting**: put a prior on the soft-pity curve and update it with your pulls, then show credible intervals.
10. **"Should I pull?" simulator**: Monte Carlo over upcoming banners with priorities (e.g. "Want X at S1, Y at S0, weapon optional").

**AI (Ollama)**
11. **Pull-log narrator**: a weekly summary ("You spent 3,200 Astrite, hit 1 × 5★ at pity 72…").
12. **RAG over game info**: local markdown notes about banners and characters, retrieved into context.
13. **Voice/tone presets**: an analyst or a hype-friend persona.
14. **Model benchmark**: compare how different Ollama models answer the same probability questions (a nice AI-course experiment on tool-calling reliability).

**App / UX**
15. Tray icon with **daily/weekly reset timers** (like the website header).
16. Light/dark theme and Dutch/English UI.
17. Auto-update check through GitHub Releases.
18. Optional cloud sync of the SQLite file via OneDrive.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Soft-pity curve is unofficial | Model choice in settings; fitted model from your own data; flat model as lower bound. |
| Game API/log format changes | Game import is isolated in one module; JSON import always works. |
| Small local LLMs make up numbers | Tools force them to use the engine; the system prompt says "never compute odds yourself". |
| Unknown banner type IDs | Names are editable; unknown types still get pity tracking. |
| Game ToS | Only reads your own log/history URL (same as wuwatracker); no memory reading or injection. |
