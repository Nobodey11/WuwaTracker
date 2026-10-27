"""Import pulls directly from the game (the same approach as wuwatracker's import script).

1. In the game, open Convene -> History once. The game writes the history link to its log files.
2. We find the game install, read the newest link from the logs and query Kuro's gacha record API for every
   banner type.

Notes
- Newer game versions XOR-scramble Client.log; it is decoded before searching (raw text is tried too).
- The install is found via the game folder from Settings, Windows registry traces (MUI cache, firewall rules,
  uninstall entries), every Steam library from Steam's libraryfolders.vdf, and common folders on all drives.
- The link expires after a while: if the API rejects it, open Convene -> History in-game again and re-import.

Only your own history link is used. No game memory is read and nothing is injected.
"""
from __future__ import annotations

import json
import os
import re
import string
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import Pull

URL_RE = re.compile(r"https://aki-gm-resources(?:-oversea)?\.aki-game\.(?:net|com)/aki/gacha/index\.html#/record[^\s\"'<>\\]*")

CLIENT_LOG = Path("Client/Saved/Logs/Client.log")
DEBUG_LOG = Path("Client/Binaries/Win64/ThirdParty/KrPcSdk_Global/KRSDKRes/KRSDKWebView/debug.log")
GAME_SUBDIRS = ("", "Wuthering Waves Game")          # launcher folder vs. game folder

COMMON_RELATIVE = [                                  # checked on every drive letter
    r"Wuthering Waves", r"Wuthering Waves Game",
    r"Program Files\Wuthering Waves", r"Program Files (x86)\Wuthering Waves",
    r"Program Files (x86)\Steam\steamapps\common\Wuthering Waves",
    r"Program Files\Steam\steamapps\common\Wuthering Waves",
    r"SteamLibrary\steamapps\common\Wuthering Waves", r"Steam\steamapps\common\Wuthering Waves",
    r"Program Files\Epic Games\WutheringWavesj3oFh", r"Epic Games\WutheringWavesj3oFh",
    r"Games\Wuthering Waves",
]

API_GLOBAL = "https://gmserver-api.aki-game2.net/gacha/record/query"
API_CN = "https://gmserver-api.aki-game2.com/gacha/record/query"
POOL_TYPES = range(1, 13)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0.0.0 Safari/537.36")

# Server time zones (the API returns server-local timestamps without an offset)
SERVER_UTC_OFFSET = {"Europe": 1, "America": -5, "Asia": 8, "HMT (Hong Kong, Macau, Taiwan)": 8, "SEA": 8}


class ImportError_(RuntimeError):
    """Readable error shown to the user."""


# ---------------------------------------------------------------- finding the install
def _registry_candidates() -> list[Path]:
    if not sys.platform.startswith("win"):
        return []
    import winreg
    out: list[Path] = []

    def values(root, path):
        try:
            with winreg.OpenKey(root, path) as k:
                i = 0
                while True:
                    try:
                        yield winreg.EnumValue(k, i)
                    except OSError:
                        return
                    i += 1
        except OSError:
            return

    def trim_client(p: str):
        low = p.lower()
        if "\\client\\" in low:
            out.append(Path(p[: low.index("\\client\\")]))

    # 1. MUI cache: names like 'D:\...\Client\Binaries\Win64\Client-Win64-Shipping.exe.FriendlyAppName'
    for name, _val, _t in values(winreg.HKEY_CURRENT_USER,
                                 r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"):
        if "client-win64-shipping.exe" in name.lower():
            trim_client(name)
    # 2. Firewall rules: '...|App=D:\...\Client-Win64-Shipping.exe|...'
    for _name, val, _t in values(winreg.HKEY_LOCAL_MACHINE,
                                 r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"):
        if isinstance(val, str) and "client-win64-shipping.exe" in val.lower():
            m = re.search(r"App=([^|]+)", val)
            if m:
                trim_client(m.group(1))
    # 3. Uninstall entries
    for hive, base in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            with winreg.OpenKey(hive, base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sub:
                            name = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                            if "wuthering" not in name.lower():
                                continue
                            for v in ("InstallPath", "InstallLocation"):
                                try:
                                    out.append(Path(winreg.QueryValueEx(sub, v)[0]))
                                except OSError:
                                    pass
                    except OSError:
                        continue
        except OSError:
            pass
    return out


def _steam_candidates() -> list[Path]:
    """Every Steam library from libraryfolders.vdf (handles libraries in custom folders)."""
    roots: list[Path] = []
    if sys.platform.startswith("win"):
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    roots.append(Path(winreg.QueryValueEx(k, val)[0]))
            except OSError:
                pass
    roots += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")]
    libs: list[Path] = []
    for r in roots:
        vdf = r / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        libs.append(r)
        libs += steam_libraries_from_vdf(text)
    return [lib / "steamapps" / "common" / "Wuthering Waves" for lib in libs]


def steam_libraries_from_vdf(text: str) -> list[Path]:
    """Library folders listed in Steam's libraryfolders.vdf ("path"  "D:\\\\Platforms\\\\Steam")."""
    return [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', text)]


def _drive_candidates() -> list[Path]:
    if not sys.platform.startswith("win"):
        return []
    out = []
    for d in string.ascii_uppercase:
        root = Path(f"{d}:\\")
        if root.exists():
            out += [root / rel for rel in COMMON_RELATIVE]
    return out


def candidate_dirs(game_dir: str | None = None) -> list[Path]:
    """All plausible install folders, most specific first, de-duplicated."""
    cands: list[Path] = []
    if game_dir:
        p = Path(game_dir)
        cands.append(p.parent.parent.parent if p.name.lower() == "client.log" else p)
    for fn in (_registry_candidates, _steam_candidates, _drive_candidates):
        try:
            cands += fn()
        except Exception:
            pass
    seen, out = set(), []
    for c in cands:
        if "onedrive" in str(c).lower():
            continue
        for sub in GAME_SUBDIRS:
            d = (c / sub) if sub else c
            k = str(d).lower()
            if k not in seen:
                seen.add(k)
                out.append(d)
    return out


def find_logs(game_dir: str | None = None) -> list[Path]:
    """Existing Client.log / debug.log files, newest first."""
    logs = []
    for d in candidate_dirs(game_dir):
        for rel in (CLIENT_LOG, DEBUG_LOG):
            f = d / rel
            try:
                if f.is_file():
                    logs.append(f)
            except OSError:
                pass
    return sorted(set(logs), key=lambda f: f.stat().st_mtime, reverse=True)


# ---------------------------------------------------------------- reading the link
def decode_client_log(data: bytes) -> bytes:
    """Undo the XOR scrambling of newer Client.log files: odd low nibble -> ^0xA5, otherwise ^0xEF."""
    table = bytes((b ^ 0xA5) if (b & 0x0F) % 2 == 1 else (b ^ 0xEF) for b in range(256))
    return data.translate(table)


def find_url_in_bytes(data: bytes) -> str | None:
    """Last convene link in the data, trying the decoded and the raw form."""
    for blob in (decode_client_log(data), data):
        text = blob.decode("utf-8", errors="ignore")
        urls = URL_RE.findall(text)
        if urls:
            return urls[-1]
    return None


@dataclass
class UrlSearch:
    url: str | None = None
    source: Path | None = None
    checked: list[Path] = field(default_factory=list)


def find_gacha_url(game_dir: str | None = None) -> UrlSearch:
    res = UrlSearch()
    for f in find_logs(game_dir):
        res.checked.append(f)
        try:
            data = f.read_bytes()
        except OSError:
            continue
        url = find_url_in_bytes(data)
        if url:
            res.url, res.source = url, f
            return res
    return res


def parse_gacha_url(url: str) -> dict:
    url = url.strip().strip('"')
    frag = urlparse(url).fragment            # "/record?svr_id=...&player_id=..."
    q = parse_qs(frag.split("?", 1)[1] if "?" in frag else "")
    g = lambda k: q.get(k, [""])[0]
    params = {"playerId": g("player_id"), "serverId": g("svr_id"), "languageCode": g("lang") or "en",
              "cardPoolId": g("resources_id"), "recordId": g("record_id")}
    missing = [k for k, v in params.items() if not v]
    if missing:
        raise ImportError_(f"That doesn't look like a complete Convene history link (missing {', '.join(missing)}).")
    oversea = "-oversea" in url
    params["api"] = API_GLOBAL if oversea or ".net/" in url else API_CN
    origin = "https://aki-gm-resources-oversea.aki-game.net" if oversea else "https://aki-gm-resources.aki-game.com"
    params["headers"] = {"Content-Type": "application/json", "User-Agent": UA,
                         "Origin": origin, "Referer": origin + "/"}
    return params


# ---------------------------------------------------------------- API
def fetch_pool(params: dict, pool_type: int, timeout: float = 15) -> list[dict]:
    body = {k: params[k] for k in ("playerId", "serverId", "languageCode", "cardPoolId", "recordId")}
    body["cardPoolType"] = pool_type
    req = urllib.request.Request(params["api"], data=json.dumps(body).encode(), headers=params["headers"])
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}") from e
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


def detect_offset(records_by_pool: dict[int, list[dict]], existing: dict[int, set], default: float) -> float:
    """Find the server time zone by matching API records with already stored pulls (time+resourceId)."""
    best, best_hits = default, 0
    for off in range(-12, 15):
        hits = 0
        for pt, recs in records_by_pool.items():
            have = existing.get(pt)
            if not have:
                continue
            for p in records_to_pulls(recs, pt, "", off):
                hits += (p.time, p.resource_id) in have
        if hits > best_hits:
            best, best_hits = off, hits
    return best


@dataclass
class GameImportResult:
    pulls: list[Pull]
    player_id: str
    offset: float
    log: list[str]


def import_from_game(url: str, utc_offset_h: float, existing_pulls: list[Pull] | None = None,
                     log=print) -> GameImportResult:
    """Fetch every banner. Pulls already stored are recognised by (banner, time, item), and the server time zone
    is auto-detected from them, so re-importing never duplicates anything."""
    params = parse_gacha_url(url)
    lines: list[str] = []

    def say(s):
        lines.append(s)
        log(s)

    recs_by_pool, errors = {}, {}
    for pt in POOL_TYPES:
        try:
            recs_by_pool[pt] = fetch_pool(params, pt)
        except Exception as e:
            errors[pt] = str(e)
    if not recs_by_pool:
        first = next(iter(errors.values()), "no response")
        raise ImportError_(f"The game server rejected the history link ({first}).\n\nThe link has probably expired: open "
                           "Convene → History in the game again, then import within a few minutes.")
    existing = {}
    for p in existing_pulls or []:
        existing.setdefault(p.pool_type, set()).add((p.time, p.resource_id))
    offset = detect_offset(recs_by_pool, existing, utc_offset_h) if existing else utc_offset_h
    if offset != utc_offset_h:
        say(f"Server time zone detected from your existing pulls: UTC{offset:+g}")
    pulls = []
    for pt, recs in recs_by_pool.items():
        ps = records_to_pulls(recs, pt, params["playerId"], offset)
        have = existing.get(pt, set())
        new = [p for p in ps if (p.time, p.resource_id) not in have]
        if recs:
            say(f"  type {pt}: {len(recs)} records from game, {len(new)} new")
        pulls.extend(new)
    return GameImportResult(pulls, params["playerId"], offset, lines)
