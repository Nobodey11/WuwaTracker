"""EXPERIMENTAL: import directly from the game, the same way wuwatracker's import script works.

1. In the game, open Convene -> History once (this writes a URL to the game's log file).
2. We read that URL from the log, then query Kuro's gacha record API for every banner type.

Only your own history URL is used. No game memory is read and nothing is injected.
"""
from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import Pull

URL_RE = re.compile(r"https://aki-gm-resources(?:-oversea)?\.aki-game\.(?:net|com)/aki/gacha/index\.html#/record[^\s\"'<>]*")

LOG_SUBPATHS = [
    "Client/Saved/Logs/Client.log",
    "Wuthering Waves Game/Client/Saved/Logs/Client.log",
    "Client/Binaries/Win64/ThirdParty/KrPcSdk_Global/KRSDKRes/KRSDKWebView/debug.log",
    "Wuthering Waves Game/Client/Binaries/Win64/ThirdParty/KrPcSdk_Global/KRSDKRes/KRSDKWebView/debug.log",
]

COMMON_INSTALLS = [
    r"C:\Wuthering Waves", r"D:\Wuthering Waves", r"E:\Wuthering Waves",
    r"C:\Program Files\Wuthering Waves", r"D:\Program Files\Wuthering Waves",
    r"C:\Program Files (x86)\Steam\steamapps\common\Wuthering Waves",
    r"D:\SteamLibrary\steamapps\common\Wuthering Waves",
    r"C:\Program Files\Epic Games\WutheringWavesj3oFh",
]

API_GLOBAL = "https://gmserver-api.aki-game2.net/gacha/record/query"
API_CN = "https://gmserver-api.kurogame.com/gacha/record/query"
POOL_TYPES = range(1, 13)

# Server time zones (API returns server-local timestamps without offset)
SERVER_UTC_OFFSET = {"Europe": 1, "America": -5, "Asia": 8, "HMT (Hong Kong, Macau, Taiwan)": 8, "SEA": 8}


def find_gacha_url(game_dir: str | None = None) -> str | None:
    roots = [game_dir] if game_dir else COMMON_INSTALLS
    best: tuple[float, str] | None = None
    for root in roots:
        if not root:
            continue
        for sub in LOG_SUBPATHS:
            f = Path(root) / sub
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            urls = URL_RE.findall(text)
            if urls and (best is None or f.stat().st_mtime > best[0]):
                best = (f.stat().st_mtime, urls[-1])
    return best[1] if best else None


def parse_gacha_url(url: str) -> dict:
    frag = urlparse(url).fragment            # "/record?svr_id=...&player_id=..."
    q = parse_qs(frag.split("?", 1)[1] if "?" in frag else "")
    g = lambda k: q.get(k, [""])[0]
    return {"playerId": g("player_id"), "serverId": g("svr_id"), "languageCode": g("lang") or "en",
            "cardPoolId": g("resources_id"), "recordId": g("record_id"),
            "api": API_CN if "aki-game.com" in url and "oversea" not in url else API_GLOBAL}


def fetch_pool(params: dict, pool_type: int, timeout: float = 15) -> list[dict]:
    body = {k: params[k] for k in ("playerId", "serverId", "languageCode", "cardPoolId", "recordId")}
    body["cardPoolType"] = pool_type
    req = urllib.request.Request(params["api"], data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    if data.get("code") != 0:
        raise RuntimeError(data.get("message") or f"API code {data.get('code')}")
    return data.get("data") or []


def records_to_pulls(records: list[dict], pool_type: int, player_id: str, utc_offset_h: float) -> list[Pull]:
    """API returns newest first. Within one 10-pull (same timestamp) the first item is the last pull,
    which matches wuwatracker's group numbering (10 = last)."""
    tz = timezone(timedelta(hours=utc_offset_h))
    per_time = Counter(r["time"] for r in records)
    seen: Counter = Counter()
    out = []
    for r in records:
        t = r["time"]
        group = per_time[t] - seen[t]
        seen[t] += 1
        dt = datetime.strptime(t, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz).astimezone(timezone.utc)
        out.append(Pull(pool_type=pool_type, resource_id=int(r["resourceId"]), quality=int(r["qualityLevel"]),
                        name=r["name"], time=dt, group=group, player_id=player_id))
    return out


def import_from_game(url: str, utc_offset_h: float, existing_latest: dict[int, datetime] | None = None,
                     log=print) -> tuple[list[Pull], str]:
    """Fetch all banners. Only keeps pulls newer than what is already stored (per banner), so a
    slightly wrong time-zone can never create duplicates of old pulls."""
    params = parse_gacha_url(url)
    existing_latest = existing_latest or {}
    pulls: list[Pull] = []
    for pt in POOL_TYPES:
        try:
            recs = fetch_pool(params, pt)
        except Exception as e:
            log(f"  type {pt}: skipped ({e})")
            continue
        ps = records_to_pulls(recs, pt, params["playerId"], utc_offset_h)
        cutoff = existing_latest.get(pt)
        if cutoff:
            ps = [p for p in ps if p.time > cutoff]
        log(f"  type {pt}: {len(recs)} records from game, {len(ps)} new")
        pulls.extend(ps)
    return pulls, params["playerId"]
