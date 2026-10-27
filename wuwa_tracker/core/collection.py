"""Collection: every resonator and weapon, with what you own (sequence S0–S6, refinement R1–R5)."""
from __future__ import annotations

from dataclasses import dataclass

from .prydwen import key

WEAPON_ID_MIN = 100000


@dataclass
class Item:
    name: str
    kind: str              # "resonator" or "weapon"
    rarity: int
    group: str             # element (resonators) or weapon type (weapons)
    copies: int
    icon: str = ""
    resource_id: int = 0
    limited: bool | None = None

    @property
    def owned(self) -> bool:
        return self.copies > 0

    @property
    def level(self) -> str:
        if not self.copies:
            return ""
        if self.kind == "resonator":
            return f"S{min(6, self.copies - 1)}" + ("+" if self.copies > 7 else "")
        return f"R{min(5, self.copies)}" + ("+" if self.copies > 5 else "")


def build(pulls, extras: dict[str, int], char_list: dict[str, dict], weapon_list: dict[str, dict],
          gd=None) -> list[Item]:
    items: dict[tuple[str, str], Item] = {}
    lim_res = set(gd.raw.get("limited_5star_resonators", [])) if gd else set()
    lim_wep = set(gd.raw.get("limited_5star_weapons", [])) if gd else set()
    std = set(gd.raw.get("standard_5star_resonators", [])) | set(gd.raw.get("standard_5star_weapons", [])) if gd else set()

    def lim(name, rarity):
        if rarity != 5 or not gd:
            return None
        return True if name in lim_res or name in lim_wep else (False if name in std else None)

    for c in char_list.values():
        items[("resonator", key(c["name"]))] = Item(c["name"], "resonator", c.get("rarity") or 0, c.get("element", ""),
                                                   0, c.get("card", ""), 0, lim(c["name"], c.get("rarity")))
    for w in weapon_list.values():
        items[("weapon", key(w["name"]))] = Item(w["name"], "weapon", w.get("rarity") or 0, w.get("type", ""), 0,
                                                w.get("icon", ""), w.get("resource_id", 0), lim(w["name"], w.get("rarity")))
    for p in pulls:
        if p.quality < 4:
            continue
        kind = "weapon" if p.resource_id >= WEAPON_ID_MIN else "resonator"
        k = (kind, key(p.name))
        if k not in items:
            items[k] = Item(p.name, kind, p.quality, "", 0, "", p.resource_id if kind == "weapon" else 0,
                            lim(p.name, p.quality))
        items[k].copies += 1
        if kind == "weapon" and not items[k].resource_id:
            items[k].resource_id = p.resource_id
    for name, n in (extras or {}).items():
        k = ("weapon", key(name)) if ("weapon", key(name)) in items else ("resonator", key(name))
        if k not in items:
            items[k] = Item(name, k[0], 0, "", 0)
        items[k].copies += int(n)
    return sorted(items.values(), key=lambda i: (i.kind != "resonator", -i.rarity, not i.owned, i.name.lower()))


def summary(items: list[Item]) -> dict:
    out = {}
    for kind in ("resonator", "weapon"):
        for r in (5, 4):
            sel = [i for i in items if i.kind == kind and i.rarity == r]
            out[f"{kind}_{r}"] = (sum(1 for i in sel if i.owned), len(sel))
    return out
