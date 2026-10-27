"""Convene Simulator extras: achievements and a session leaderboard (just for fun)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Achievement:
    id: str
    title: str
    text: str


ACHIEVEMENTS = [
    Achievement("first_gold", "First gold", "Pull your first 5★ in the simulator."),
    Achievement("early_bird", "Early bird", "Get a 5★ before pity 20."),
    Achievement("double_gold", "Double gold", "Two 5★s in one 10-pull."),
    Achievement("triple_gold", "Jackpot", "Three or more 5★s in one 10-pull."),
    Achievement("win_streak", "Coin master", "Win three 50/50s in a row."),
    Achievement("lose_streak", "Verina's favourite", "Lose three 50/50s in a row."),
    Achievement("hard_pity", "Hard pity club", "Reach pity 80."),
    Achievement("whale", "Whale mode", "Do 1,000 pulls in one session."),
    Achievement("s6", "Full sequence", "Get 7 copies of the featured 5★ in one session."),
    Achievement("weapon_r5", "R5 dreams", "Get 5 copies of a featured 5★ weapon in one session."),
    Achievement("all_purple", "Purple rain", "Five or more 4★s in one 10-pull."),
]
BY_ID = {a.id: a for a in ACHIEVEMENTS}


def check(batch, sim) -> list[str]:
    """Achievement ids earned by this batch (a list of SimItem) given the simulator state after it."""
    got = []
    fives = [i for i in batch if i.rarity == 5]
    s = sim.stats
    if fives and s.five == len(fives):
        got.append("first_gold")
    if any(i.pity < 20 for i in fives):
        got.append("early_bird")
    if len(batch) >= 10 and len(fives) == 2:
        got.append("double_gold")
    if len(batch) >= 10 and len(fives) >= 3:
        got.append("triple_gold")
    if len(batch) >= 10 and sum(1 for i in batch if i.rarity == 4) >= 5:
        got.append("all_purple")
    if any(i.pity >= 80 for i in fives):
        got.append("hard_pity")
    results = [i.result for i in s.history if i.rarity == 5 and i.result in ("won", "lost")]
    if len(results) >= 3 and results[-3:] == ["won"] * 3:
        got.append("win_streak")
    if len(results) >= 3 and results[-3:] == ["lost"] * 3:
        got.append("lose_streak")
    if s.pulls >= 1000:
        got.append("whale")
    if s.featured5 >= 7 and not sim.weapon_banner:
        got.append("s6")
    if s.featured5 >= 5 and sim.weapon_banner:
        got.append("weapon_r5")
    return got


def leaderboard_entry(sim, label: str) -> dict | None:
    """Score a finished session: pulls per featured 5★ (lower = luckier)."""
    s = sim.stats
    if s.pulls < 10 or s.featured5 == 0:
        return None
    return {"label": label, "pulls": s.pulls, "featured": s.featured5, "per_featured": round(s.pulls / s.featured5, 1),
            "wins": s.wins, "losses": s.losses}


def add_to_board(board: list[dict], entry: dict | None, keep: int = 10) -> list[dict]:
    if not entry:
        return board
    return sorted(board + [entry], key=lambda e: (e["per_featured"], -e["featured"]))[:keep]
