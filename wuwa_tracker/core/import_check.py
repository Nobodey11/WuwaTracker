"""Sanity checks after an import: possible gaps, broken 10-pulls, and comparison with a wuwatracker export."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta

from .models import Pull


@dataclass
class Finding:
    level: str        # "warning" or "info"
    banner: int
    text: str


def check_new_vs_existing(existing: list[Pull], new: list[Pull], name=lambda pt: f"banner {pt}") -> list[Finding]:
    """A downloaded batch that doesn't overlap the stored history may have left a hole in between.
    (The game only returns recent history, so pulls older than its window can be missing.)"""
    out = []
    by_old = defaultdict(list)
    for p in existing:
        by_old[p.pool_type].append(p)
    by_new = defaultdict(list)
    for p in new:
        by_new[p.pool_type].append(p)
    for pt, ps in by_new.items():
        olds = by_old.get(pt)
        if not olds:
            continue
        newest_old = max(p.time for p in olds)
        oldest_new = min(p.time for p in ps)
        if oldest_new > newest_old + timedelta(minutes=1):
            gap = oldest_new - newest_old
            out.append(Finding("warning", pt,
                               f"{name(pt)}: the new records start {gap.days} day(s) after your last stored pull "
                               f"({newest_old:%Y-%m-%d} → {oldest_new:%Y-%m-%d}). Pulls in between may be missing; "
                               "import a wuwatracker export that covers that period to fill the gap."))
    return out


def check_ten_pulls(pulls: list[Pull], name=lambda pt: f"banner {pt}") -> list[Finding]:
    """Pulls sharing one timestamp are a multi-pull; their group numbers should be 1..n without holes."""
    out = []
    batches = defaultdict(list)
    for p in pulls:
        batches[(p.pool_type, p.time)].append(p.group)
    bad = Counter()
    for (pt, _), groups in batches.items():
        gs = sorted(g for g in groups if g)
        if len(gs) > 1 and gs != list(range(1, len(gs) + 1)):
            bad[pt] += 1
    for pt, n in bad.items():
        out.append(Finding("warning", pt, f"{name(pt)}: {n} multi-pull(s) have missing or duplicate positions."))
    return out


def compare_with_export(stored: list[Pull], export: list[Pull], name=lambda pt: f"banner {pt}") -> list[Finding]:
    """Per banner: pulls in the export that are not stored (by time + item), and the other way round."""
    out = []
    key = lambda p: (p.pool_type, p.time.replace(microsecond=0), p.resource_id)
    a, b = Counter(map(key, stored)), Counter(map(key, export))
    missing = b - a
    extra = a - b
    pts = sorted({k[0] for k in missing} | {k[0] for k in extra} | {p.pool_type for p in export})
    for pt in pts:
        m = sum(v for k, v in missing.items() if k[0] == pt)
        e = sum(v for k, v in extra.items() if k[0] == pt)
        n_exp = sum(1 for p in export if p.pool_type == pt)
        n_sto = sum(1 for p in stored if p.pool_type == pt)
        if m or e:
            out.append(Finding("warning", pt, f"{name(pt)}: app {n_sto:,} vs export {n_exp:,} pulls; "
                                              f"{m} missing in the app, {e} not in the export."))
        else:
            out.append(Finding("info", pt, f"{name(pt)}: {n_sto:,} pulls, identical."))
    return out


def summarize(findings: list[Finding]) -> str:
    if not findings:
        return "No problems found."
    return "\n".join(("⚠ " if f.level == "warning" else "✓ ") + f.text for f in findings)
