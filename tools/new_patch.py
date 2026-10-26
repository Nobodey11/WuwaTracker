"""Per-patch maintenance tool for wuwa_tracker/data/game_data.json.

Examples
  # 1. see what's new in your latest export (unknown 5★ items / banner types)
  python tools/new_patch.py scan path\\to\\wuwatracker-pulls.json

  # 2. add a banner phase (new 5★ names are automatically registered as limited)
  python tools/new_patch.py phase --patch 3.8 --phase 1 --start 2026-11-11 --end 2026-12-02 ^
         --res "NewChar, RerunA, RerunB" --weap "NewWeapon, WeapA, WeapB" --four "x, y, z"

  # 3. classify single items or banner types
  python tools/new_patch.py classify "SomeName" standard
  python tools/new_patch.py banner-type 13 "Some New Convene" event

  # 4. change the soft-pity model (if new data/official info appears)
  python tools/new_patch.py rates --steps "66:0.04,71:0.08,76:0.10"

  # 5. validate (also run by the tests)
  python tools/new_patch.py check

Every change bumps data_version (YYYY.MM.DD[.n]) so apps with your update URL pick it up.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wuwa_tracker.core.gamedata import BUNDLED, KINDS, LIST_KEYS, GameData, validate, version_tuple  # noqa: E402
from wuwa_tracker.core.storage import read_wuwatracker_json  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    today = date.today().strftime("%Y.%m.%d")
    old = data.get("data_version", "")
    if old.startswith(today):
        n = version_tuple(old)[3] if len(version_tuple(old)) > 3 else 1
        data["data_version"] = f"{today}.{n + 1}"
    else:
        data["data_version"] = today
    problems = validate(data)
    if problems:
        sys.exit("NOT saved, invalid data:\n  " + "\n  ".join(problems))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {path}  →  data_version {data['data_version']}, patch {data.get('game_patch')}")


def split(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def add_unique(lst: list, names: list[str]) -> list[str]:
    added = [n for n in names if n not in lst]
    lst.extend(added)
    return added


def cmd_scan(a, data):
    pulls, player = read_wuwatracker_json(a.export)
    items, pools = GameData(data).find_unknown(pulls)
    print(f"Export of player {player}: {len(pulls)} pulls")
    if not items and not pools:
        print("✔ Nothing new — game data already knows every 5★ and banner type.")
    for n, w in items:
        print(f"  NEW 5★ {'weapon' if w else 'resonator'}: {n}    → classify \"{n}\" limited|standard")
    for p in pools:
        print(f"  NEW banner type: {p}    → banner-type {p} \"Name\" <kind>")
    return False


def cmd_phase(a, data):
    std = set(data.get("standard_5star_resonators", [])) | set(data.get("standard_5star_weapons", []))
    res, weap, four = split(a.res), split(a.weap), split(a.four)
    data.setdefault("banners", [])
    data["banners"] = [b for b in data["banners"] if not (b["patch"] == a.patch and b.get("phase") == a.phase)]
    data["banners"].append({"patch": a.patch, "phase": a.phase, "start": a.start, "end": a.end,
                            "featured_5star_resonators": res, "featured_5star_weapons": weap,
                            "featured_4star_resonators": four})
    data["banners"].sort(key=lambda b: b["start"])
    new_r = add_unique(data.setdefault("limited_5star_resonators", []), [n for n in res if n not in std])
    new_w = add_unique(data.setdefault("limited_5star_weapons", []), [n for n in weap if n not in std])
    if version_tuple(a.patch) >= version_tuple(data.get("game_patch", "0")):
        data["game_patch"] = a.patch
    print(f"Phase {a.patch} P{a.phase} set. New limited: {new_r + new_w or 'none'}")
    return True


def cmd_classify(a, data):
    weapon = a.weapon or any(a.name in data.get(k, []) for k in ("standard_5star_weapons", "limited_5star_weapons"))
    kind = "weapons" if weapon else "resonators"
    for k in LIST_KEYS:
        if a.name in data.get(k, []):
            data[k].remove(a.name)
    data.setdefault(f"{a.cls}_5star_{kind}", []).append(a.name)
    print(f"{a.name} → {a.cls} {kind[:-1]}")
    return True


def cmd_banner_type(a, data):
    data["banner_types"][str(a.id)] = {"name": a.name, "kind": a.kind}
    print(f"banner type {a.id} = {a.name} ({a.kind})")
    return True


def cmd_rates(a, data):
    r = data["rates"]
    if a.steps:
        r["soft_pity_steps"] = [[int(x.split(":")[0]), float(x.split(":")[1])] for x in split(a.steps)]
    for k in ("base5", "base4", "hard_pity5", "hard_pity4", "astrite_per_pull"):
        v = getattr(a, k)
        if v is not None:
            r[k] = v
    print("rates:", json.dumps(r))
    return True


def cmd_check(a, data):
    problems = validate(data)
    if problems:
        sys.exit("INVALID:\n  " + "\n  ".join(problems))
    gd = GameData(data)
    cur = gd.current_banners()
    print(f"✔ valid · v{gd.version} · patch {gd.patch} · {len(data.get('banners', []))} phases · "
          f"{len(gd.known_5stars)} known 5★")
    if not cur:
        print("⚠ No banner phase covers today — add the current patch with the 'phase' command.")
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, default=BUNDLED, help="game_data.json to edit (default: bundled)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan"); p.add_argument("export"); p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("phase")
    p.add_argument("--patch", required=True); p.add_argument("--phase", type=int, required=True)
    p.add_argument("--start", required=True); p.add_argument("--end", required=True)
    p.add_argument("--res", default=""); p.add_argument("--weap", default=""); p.add_argument("--four", default="")
    p.set_defaults(fn=cmd_phase)
    p = sub.add_parser("classify"); p.add_argument("name"); p.add_argument("cls", choices=["limited", "standard"])
    p.add_argument("--weapon", action="store_true"); p.set_defaults(fn=cmd_classify)
    p = sub.add_parser("banner-type"); p.add_argument("id", type=int); p.add_argument("name")
    p.add_argument("kind", choices=KINDS); p.set_defaults(fn=cmd_banner_type)
    p = sub.add_parser("rates"); p.add_argument("--steps")
    for k, t in (("base5", float), ("base4", float), ("hard_pity5", int), ("hard_pity4", int), ("astrite_per_pull", int)):
        p.add_argument(f"--{k}", type=t)
    p.set_defaults(fn=cmd_rates)
    p = sub.add_parser("check"); p.set_defaults(fn=cmd_check)

    a = ap.parse_args(argv)
    data = load(a.file)
    if a.fn(a, data):
        save(a.file, data)


if __name__ == "__main__":
    main()
