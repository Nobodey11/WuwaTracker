"""Patch-dependent game knowledge, kept OUT of the code so it can be updated every patch.

Three layers, later ones win:
  1. bundled   wuwa_tracker/data/game_data.json             (ships with the app)
  2. remote    %APPDATA%/WuwaTracker/game_data.remote.json  (downloaded from your update URL, used if newer)
  3. user      %APPDATA%/WuwaTracker/game_data.user.json    (your own classifications from the app)

The user layer only stores small overrides:
  {"banner_types": {"13": {"name": "...", "kind": "..."}},
   "classify":     {"Suoming": "limited", "SomeNewStandardChar": "standard"}}
"""
from __future__ import annotations

import copy
import json
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

BUNDLED = Path(__file__).resolve().parent.parent / "data" / "game_data.json"
SCHEMA = 1
KINDS = ("featured_character", "featured_weapon", "standard", "beginner", "selector", "event")
LIST_KEYS = ("standard_5star_resonators", "standard_5star_weapons", "limited_5star_resonators", "limited_5star_weapons")
WEAPON_ID_MIN = 100000      # resourceId >= this is a weapon (resonators are 4-digit ids)


# ---------------------------------------------------------------- helpers
def version_tuple(v: str) -> tuple[int, ...]:
    """'2026.10.26' or '2026.10.26.2' -> (2026, 10, 26, 2). Non-numeric parts count as 0."""
    out = []
    for p in str(v).split("."):
        out.append(int(p) if p.isdigit() else 0)
    return tuple(out)


def validate(raw: dict) -> list[str]:
    """Return a list of problems (empty = valid). Used by the updater, tests and tools/new_patch.py."""
    err = []
    if raw.get("schema") != SCHEMA:
        err.append(f"schema must be {SCHEMA}")
    if not version_tuple(raw.get("data_version", ""))[:1] or version_tuple(raw.get("data_version", ""))[0] < 2024:
        err.append("data_version must look like YYYY.MM.DD")
    r = raw.get("rates", {})
    for k in ("base5", "hard_pity5", "soft_pity_steps", "base4", "hard_pity4", "astrite_per_pull"):
        if k not in r:
            err.append(f"rates.{k} missing")
    if r.get("soft_pity_steps"):
        starts = [s[0] for s in r["soft_pity_steps"]]
        if starts != sorted(starts) or any(not (1 < s < r.get("hard_pity5", 80)) for s in starts):
            err.append("rates.soft_pity_steps must be increasing pity values below hard pity")
    bt = raw.get("banner_types", {})
    if not bt:
        err.append("banner_types missing")
    for k, v in bt.items():
        if not str(k).isdigit():
            err.append(f"banner_types key {k!r} must be a number")
        if v.get("kind") not in KINDS:
            err.append(f"banner_types[{k}].kind must be one of {KINDS}")
        if not v.get("name"):
            err.append(f"banner_types[{k}].name missing")
    for k in LIST_KEYS:
        if not isinstance(raw.get(k, []), list):
            err.append(f"{k} must be a list")
    both = set(raw.get("standard_5star_resonators", [])) & set(raw.get("limited_5star_resonators", []))
    if both:
        err.append(f"resonators both standard and limited: {sorted(both)}")
    for i, b in enumerate(raw.get("banners", [])):
        try:
            s, e = date.fromisoformat(b["start"]), date.fromisoformat(b["end"])
            if e < s:
                err.append(f"banners[{i}] ends before it starts")
        except Exception:
            err.append(f"banners[{i}] needs start/end as YYYY-MM-DD")
        if not b.get("patch"):
            err.append(f"banners[{i}].patch missing")
    for i, ev in enumerate(raw.get("events", [])):
        if not ev.get("name"):
            err.append(f"events[{i}].name missing")
        try:
            date.fromisoformat(str(ev["start"])[:10]); date.fromisoformat(str(ev["end"])[:10])
        except Exception:
            err.append(f"events[{i}] needs start/end as YYYY-MM-DD")
    return err


def _read(path: Path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------- model
@dataclass
class GameData:
    raw: dict
    source: str = "bundled"
    user: dict = field(default_factory=dict)

    # ----- lookups
    @property
    def version(self) -> str:
        return self.raw.get("data_version", "?")

    @property
    def patch(self) -> str:
        return self.raw.get("game_patch", "?")

    @property
    def rates(self) -> dict:
        return self.raw["rates"]

    def banner_type(self, pt: int) -> dict:
        return self.raw["banner_types"].get(str(pt), {"name": f"Banner type {pt}", "kind": "event"})

    def name(self, pt: int) -> str:
        return self.banner_type(pt)["name"]

    def kind(self, pt: int) -> str:
        return self.banner_type(pt)["kind"]

    def has_5050(self, pt: int) -> bool:
        return self.kind(pt) == "featured_character"

    def featured_chance(self, pt: int) -> float | None:
        k = self.kind(pt)
        if k == "featured_character":
            return self.rates.get("featured_chance_character", 0.5)
        if k == "featured_weapon":
            return self.rates.get("featured_chance_weapon", 1.0)
        return None

    def featured_pools(self) -> list[int]:
        return sorted(int(k) for k, v in self.raw["banner_types"].items()
                      if v["kind"] in ("featured_character", "featured_weapon"))

    @property
    def standard_resonators(self) -> set[str]:
        return set(self.raw.get("standard_5star_resonators", []))

    @property
    def known_5stars(self) -> set[str]:
        return set().union(*(self.raw.get(k, []) for k in LIST_KEYS))

    def banners_at(self, when: datetime | date) -> list[dict]:
        d = when.date() if isinstance(when, datetime) else when
        return [b for b in self.raw.get("banners", [])
                if date.fromisoformat(b["start"]) <= d < date.fromisoformat(b["end"])]

    def patch_of(self, when: datetime | date) -> str | None:
        bs = self.banners_at(when)
        return f"{bs[0]['patch']} P{bs[0].get('phase', '?')}" if bs else None

    def current_banners(self) -> list[dict]:
        return self.banners_at(date.today())

    def upcoming_banners(self) -> list[dict]:
        today = date.today()
        return [b for b in self.raw.get("banners", []) if date.fromisoformat(b["start"]) > today]

    # ----- new-content detection
    def find_unknown(self, pulls) -> tuple[list[tuple[str, bool]], list[int]]:
        """(new 5★ items as (name, is_weapon), new banner type ids) present in pulls but not in the data."""
        known = self.known_5stars
        items, pools = {}, set()
        for p in pulls:
            if str(p.pool_type) not in self.raw["banner_types"]:
                pools.add(p.pool_type)
            if p.quality == 5 and p.name not in known:
                items[p.name] = p.resource_id >= WEAPON_ID_MIN
        return sorted(items.items()), sorted(pools)


# ---------------------------------------------------------------- layering
def _apply_user(base: dict, user: dict) -> dict:
    data = copy.deepcopy(base)
    for k, v in (user.get("banner_types") or {}).items():
        data["banner_types"][str(k)] = {**data["banner_types"].get(str(k), {}), **v}
    for name, cls in (user.get("classify") or {}).items():
        is_weapon = name in data.get("standard_5star_weapons", []) or name in data.get("limited_5star_weapons", [])
        is_weapon = is_weapon or (user.get("weapons") and name in user["weapons"])
        kind = "weapons" if is_weapon else "resonators"
        for k in LIST_KEYS:
            if name in data.get(k, []):
                data[k].remove(name)
        data.setdefault(f"{cls}_5star_{kind}", []).append(name)
    return data


class GameDataStore:
    """Loads/saves the three layers and talks to the update URL."""

    def __init__(self, app_dir: Path, bundled: Path = BUNDLED):
        self.app_dir = Path(app_dir)
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.bundled_path = Path(bundled)
        self.remote_path = self.app_dir / "game_data.remote.json"
        self.user_path = self.app_dir / "game_data.user.json"

    def load(self) -> GameData:
        base, source = _read(self.bundled_path), "bundled"
        remote = _read(self.remote_path)
        if remote and not validate(remote) and version_tuple(remote["data_version"]) > version_tuple(base["data_version"]):
            base, source = remote, "downloaded"
        user = _read(self.user_path) or {}
        return GameData(_apply_user(base, user), source, user)

    # ----- user overrides
    def save_user(self, user: dict) -> None:
        self.user_path.write_text(json.dumps(user, indent=2, ensure_ascii=False), encoding="utf-8")

    def classify(self, name: str, cls: str, is_weapon: bool = False) -> None:
        assert cls in ("standard", "limited")
        u = _read(self.user_path) or {}
        u.setdefault("classify", {})[name] = cls
        if is_weapon:
            u.setdefault("weapons", [])
            if name not in u["weapons"]:
                u["weapons"].append(name)
        self.save_user(u)

    def set_banner_type(self, pt: int, name: str, kind: str) -> None:
        assert kind in KINDS
        u = _read(self.user_path) or {}
        u.setdefault("banner_types", {})[str(pt)] = {"name": name, "kind": kind}
        self.save_user(u)

    # ----- remote update
    def check_update(self, url: str, timeout: float = 10) -> tuple[bool, str]:
        """Download game data from `url`. Returns (updated?, message)."""
        if not url:
            return False, "No update URL set (Settings → Game data update URL)."
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WuwaTracker"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return False, f"Update check failed: {e}"
        problems = validate(raw)
        if problems:
            return False, "Downloaded data is invalid: " + "; ".join(problems[:3])
        current = self.load()
        if version_tuple(raw["data_version"]) <= version_tuple(current.version):
            return False, f"Game data is up to date (v{current.version}, patch {current.patch})."
        self.remote_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, f"Updated game data to v{raw['data_version']} (patch {raw.get('game_patch', '?')})."
