"""Check GitHub Releases for a newer app version."""
from __future__ import annotations

import json
import re
import urllib.request

REPO = "Nobodey11/WuwaTracker"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases"


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def latest_release(timeout: float = 8) -> dict:
    req = urllib.request.Request(API, headers={"User-Agent": "WuwaTracker", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    assets = [{"name": a.get("name"), "url": a.get("browser_download_url")} for a in d.get("assets", [])]
    return {"tag": d.get("tag_name", ""), "name": d.get("name") or d.get("tag_name", ""),
            "url": d.get("html_url") or RELEASES, "notes": d.get("body") or "", "assets": assets}


def check(local_version: str, fetch=latest_release) -> tuple[bool, dict | str]:
    """(update available?, release info or error text)."""
    try:
        rel = fetch()
    except Exception as e:
        return False, f"Update check failed: {e}"
    return is_newer(rel["tag"], local_version), rel
