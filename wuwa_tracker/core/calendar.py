"""Calendar (banners, resets, events) and the banner rerun tracker.

Sources, merged:
  * Prydwen's banner page (current + upcoming, exact per-region times), cached and remembered over time
  * the banner calendar in game_data.json (`banners`) and optional `events` [{name, start, end, note}]
  * your own events (Settings → stored in the app)
  * daily / weekly resets for your server region
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

REGION_KEY = {"Europe": "eu", "America": "na", "Asia": "asia", "HMT (Hong Kong, Macau, Taiwan)": "asia", "SEA": "asia"}


@dataclass
class Entry:
    title: str
    kind: str                 # "banner", "weapon banner", "event", "reset", "my event"
    start: datetime | None
    end: datetime | None
    detail: str = ""
    art: str = ""

    def status(self, now: datetime) -> str:
        if self.start and now < self.start:
            return "upcoming"
        if self.end and now >= self.end:
            return "ended"
        return "live"


def _dt(s: str | None, offset_h: float = 0.0, end_of_day: bool = False) -> datetime | None:
    """ISO string -> aware datetime. Plain dates are read as server-local (04:00 reset for starts)."""
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        if len(s) <= 10:
            d = date.fromisoformat(s)
            tz = timezone(timedelta(hours=offset_h))
            return datetime(d.year, d.month, d.day, 4 if not end_of_day else 3, 59 if end_of_day else 0, tzinfo=tz)
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone(timedelta(hours=offset_h)))
    except ValueError:
        return None


def resets(offset_h: float, now: datetime | None = None) -> list[Entry]:
    tz = timezone(timedelta(hours=offset_h))
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    daily = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if daily <= now:
        daily += timedelta(days=1)
    weekly = daily + timedelta(days=(0 - daily.weekday()) % 7)
    month = (now.replace(day=1, hour=4, minute=0, second=0, microsecond=0) + timedelta(days=32)).replace(day=1)
    return [Entry("Daily reset", "reset", None, daily, "Daily activity, Waveplate shop, dailies"),
            Entry("Weekly reset", "reset", None, weekly, "Weekly bosses, weekly challenges"),
            Entry("Monthly reset", "reset", None, month, "Monthly shop restock")]


def build(gd_raw: dict, prydwen_banners: list[dict], user_events: list[dict], region: str, offset_h: float,
          now: datetime | None = None, include_ended_days: int = 0) -> list[Entry]:
    from .prydwen import banner_times
    now = now or datetime.now(timezone.utc)
    rk = REGION_KEY.get(region, "asia")
    out: list[Entry] = []
    seen = set()
    for b in prydwen_banners or []:
        s, e = banner_times(b, rk)
        kind = "weapon banner" if b.get("category") == "weapon" else "banner"
        tag = ("rerun" if b.get("rerun") else "new") + (f" · Patch {b['patch']}" if b.get("patch") else "")
        if b.get("phase"):
            tag += f" P{b['phase']}"
        detail = tag + (" · with " + ", ".join(b["secondary"]) if b.get("secondary") else "")
        out.append(Entry(b["name"], kind, _dt(s), _dt(e), detail, b.get("art", "")))
        seen.add(b["name"].strip().lower())
    for b in gd_raw.get("banners", []):
        st, en = _dt(b.get("start"), offset_h), _dt(b.get("end"), offset_h)
        label = f"Patch {b.get('patch')} P{b.get('phase', '?')}"
        for n in b.get("featured_5star_resonators", []):
            if n.lower() not in seen:
                out.append(Entry(n, "banner", st, en, label + " (game data)"))
        for n in b.get("featured_5star_weapons", []):
            if n.lower() not in seen:
                out.append(Entry(n, "weapon banner", st, en, label + " (game data)"))
    for ev in gd_raw.get("events", []):
        out.append(Entry(ev.get("name", "Event"), "event", _dt(ev.get("start"), offset_h),
                         _dt(ev.get("end"), offset_h, True), ev.get("note", "")))
    for ev in user_events or []:
        out.append(Entry(ev.get("name", "My event"), "my event", _dt(ev.get("start"), offset_h),
                         _dt(ev.get("end"), offset_h, True), ev.get("note", "")))
    out += resets(offset_h, now)
    cutoff = now - timedelta(days=include_ended_days)
    out = [e for e in out if not e.end or e.end >= cutoff]
    far = datetime(9999, 1, 1, tzinfo=timezone.utc)
    order = {"live": 0, "upcoming": 1, "ended": 2}
    return sorted(out, key=lambda e: (order[e.status(now)], e.end or e.start or far, e.title))


def ending_soon(entries: list[Entry], now: datetime, within: timedelta = timedelta(days=2)) -> list[Entry]:
    return [e for e in entries if e.kind in ("banner", "weapon banner", "event", "my event")
            and e.end and now <= e.end <= now + within and e.status(now) == "live"]


# ---------------------------------------------------------------- rerun tracker
@dataclass
class RunInfo:
    name: str
    runs: list[tuple[date, date | None, str]]     # (start, end, source)
    live: bool
    upcoming: bool

    @property
    def last_end(self) -> date | None:
        ends = [e or s for s, e, _ in self.runs]
        return max(ends) if ends else None

    def days_since(self, today: date) -> int | None:
        if self.live:
            return 0
        le = self.last_end
        return (today - le).days if le else None

    @property
    def avg_gap(self) -> float | None:
        starts = sorted({s for s, _, _ in self.runs})
        if len(starts) < 2:
            return None
        return sum((b - a).days for a, b in zip(starts, starts[1:])) / (len(starts) - 1)


def rerun_tracker(limited: list[str], gd_raw: dict, prydwen_banners: list[dict], prydwen_history: list[dict],
                  pulls, today: date | None = None, featured_pool: int = 1) -> list[RunInfo]:
    """Known banner runs per limited 5★ resonator, from game data, Prydwen (now and remembered) and your own
    featured-banner pulls of that character (a pull proves the banner ran that day)."""
    from .prydwen import banner_times
    today = today or date.today()
    runs: dict[str, dict[date, tuple]] = {n: {} for n in limited}

    def add(name, s: date, e: date | None, src):
        if name not in runs:
            return
        # merge with a known run that this date falls in (same banner seen by two sources, or a pull during it)
        for k in list(runs[name]):
            ks0, ke0, _ = runs[name][k]
            if ks0 - timedelta(days=7) <= s <= (ke0 or ks0) + timedelta(days=7):
                ks, ke, ksrc = runs[name][k]
                runs[name][k] = (min(ks, s), max(filter(None, (ke, e)), default=None), ksrc)
                return
        runs[name][s] = (s, e, src)

    for b in gd_raw.get("banners", []):
        for n in b.get("featured_5star_resonators", []):
            add(n, date.fromisoformat(b["start"]), date.fromisoformat(b["end"]), "game data")
    for h in prydwen_history or []:
        if h.get("category") == "character" and h.get("start"):
            add(h["name"], date.fromisoformat(h["start"]), date.fromisoformat(h["end"]) if h.get("end") else None,
                "Prydwen")
    live, upcoming = set(), set()
    for b in prydwen_banners or []:
        if b.get("category") != "character":
            continue
        s, e = banner_times(b)
        if b.get("section") == "current":
            live.add(b["name"])
        elif b.get("section") == "upcoming":
            upcoming.add(b["name"])
        if s:
            add(b["name"], date.fromisoformat(s[:10]), date.fromisoformat(e[:10]) if e else None, "Prydwen")
    for p in pulls or []:
        if p.pool_type == featured_pool and p.quality == 5 and p.name in runs:
            d = p.time.date()
            add(p.name, d, None, "your pulls")
    for b in gd_raw.get("banners", []):
        if date.fromisoformat(b["start"]) <= today < date.fromisoformat(b["end"]):
            live.update(b.get("featured_5star_resonators", []))
        elif date.fromisoformat(b["start"]) > today:
            upcoming.update(b.get("featured_5star_resonators", []))
    out = [RunInfo(n, sorted(v.values()), n in live, n in upcoming) for n, v in runs.items()]
    # live first, then upcoming, then the longest time since the last run (likeliest rerun candidates)
    def order(r):
        ds = r.days_since(today)
        return (0 if r.live else 1 if r.upcoming else 2, -(ds if ds is not None else -1), r.name)
    return sorted(out, key=order)
