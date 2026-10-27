"""Prydwen.gg integration: tier list, character info and portraits.

All content belongs to Prydwen.gg (text/ratings) and Kuro Games (art). The app only fetches it on
request for personal viewing, caches it locally (so Prydwen isn't hammered) and always links back
to the full guide on prydwen.gg. Nothing from Prydwen is stored in the repository.

Pages are server-rendered HTML, parsed with the standard library only.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.prydwen.gg"
TIER_URL = BASE + "/wuthering-waves/tier-list"
CHARS_URL = BASE + "/wuthering-waves/characters"
CHAR_URL = BASE + "/wuthering-waves/characters/{slug}"
CODES_URL = BASE + "/wuthering-waves/codes"
BANNERS_URL = BASE + "/wuthering-waves/banners"
WEAPONS_URL = BASE + "/wuthering-waves/weapons"
WEAPON_ICON = "https://cdn.prydwen.gg/images/wuthering-waves/weapons/{rid}.webp"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WuwaTracker/0.3 (+https://github.com/Nobodey11/WuwaTracker)"

TTL_TIER = 12 * 3600          # tier list: refresh at most twice a day
TTL_CHAR = 3 * 24 * 3600      # character pages: every 3 days
TTL_CODES = 3 * 3600          # redemption codes: every 3 hours
TTL_BANNERS = 6 * 3600        # banner schedule: every 6 hours
TTL_WEAPONS = 7 * 24 * 3600   # weapon list: weekly
ROLE_LABEL = {"dps": "DPS", "debuffer": "Hybrid", "support": "Support"}
WEAPON_ID_MIN = 100000


def key(name: str) -> str:
    """Normalise names so 'Yangyang: Xuanling' == 'Yangyang Xuanling' == 'yangyang-xuanling'."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


# ---------------------------------------------------------------- tiny DOM
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def has_class(self, *names) -> bool:
        c = self.classes
        return all(n in c for n in names)

    def iter(self):
        for ch in self.children:
            if isinstance(ch, Node):
                yield ch
                yield from ch.iter()

    def find_all(self, tag=None, cls=None, pred=None):
        out = []
        for n in self.iter():
            if tag and n.tag != tag:
                continue
            if cls and not n.has_class(*cls.split()):
                continue
            if pred and not pred(n):
                continue
            out.append(n)
        return out

    def find(self, tag=None, cls=None, pred=None):
        r = self.find_all(tag, cls, pred)
        return r[0] if r else None

    def text(self) -> str:
        parts = []
        for ch in self.children:
            parts.append(ch.text() if isinstance(ch, Node) else ch)
        return "".join(parts)

    def clean_text(self) -> str:
        return re.sub(r"\s+", " ", self.text()).strip()


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root
        self.skip = 0  # inside <script>/<style>

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        if self.skip:
            return
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        if not self.skip and tag not in ("script", "style"):
            self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag in VOID:
            return
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if not self.skip:
            self.cur.children.append(data)


def parse_html(html: str) -> Node:
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


# ---------------------------------------------------------------- models
@dataclass
class TierEntry:
    tier: str
    role: str
    name: str
    slug: str
    icon: str = ""
    element: str = ""
    rarity: int = 0
    sequence: str = ""        # sequence the rating assumes (S0…)
    tags: list[str] = field(default_factory=list)
    mark: str = ""            # "up", "down", "new" or ""


@dataclass
class TierList:
    tiers: list[str]
    entries: list[TierEntry]
    fetched: float = 0.0
    mode: str = "Tower of Adversity"

    def by_key(self) -> dict[str, TierEntry]:
        """Best (first) entry per character."""
        out = {}
        for e in self.entries:
            out.setdefault(key(e.name), e)
            out.setdefault(key(e.slug), e)
        return out


@dataclass
class CharacterInfo:
    name: str
    slug: str
    url: str
    element: str = ""
    rarity: int = 0
    updated: str = ""
    card: str = ""            # portrait card image url
    roles: list[dict] = field(default_factory=list)      # {role, sequence, ratings:{label: tier}}
    weapons: list[dict] = field(default_factory=list)    # {name, refine, rarity, icon}
    echo_sets: list[dict] = field(default_factory=list)  # {name, icon}
    fetched: float = 0.0


# ---------------------------------------------------------------- parsers
def _rarity(node: Node) -> int:
    for c in node.classes:
        m = re.match(r"rarity-(\d)", c)
        if m:
            return int(m.group(1))
    return 0


def parse_tier_list(html: str) -> TierList:
    root = parse_html(html)
    tl = root.find("div", "custom-tier-list-ww")
    if tl is None:
        raise ValueError("Tier list not found on the page (Prydwen layout changed?)")
    tiers, entries = [], []
    for row in tl.find_all("div", "custom-tier"):
        r = row.find("div", "tier-rating")
        tier = r.clean_text() if r else "?"
        tiers.append(tier)
        for burst in row.find_all("div", "custom-tier-burst"):
            role = next((ROLE_LABEL.get(c, c) for c in burst.classes if c != "custom-tier-burst"), "")
            for a in burst.find_all("a", pred=lambda n: "/wuthering-waves/characters/" in n.attrs.get("href", "")):
                avatar = a.find("div", "avatar")
                imgs = a.find_all("img")
                portrait = imgs[0] if imgs else None
                elem = a.find("span", "ww-element-tl")
                elem_img = elem.find("img") if elem else None
                seq = a.find("span", "sequence")
                marks = a.find("span", "tier-marks")
                mark = ""
                if marks:
                    mark = next((c for c in marks.classes if c in ("up", "down", "new")), "")
                tags_div = a.find("div", "tier-list-tags")
                tags = [t.clean_text().rstrip(",").strip() for t in tags_div.find_all("span", "single-tag")] if tags_div else []
                entries.append(TierEntry(
                    tier=tier, role=role,
                    name=(portrait.attrs.get("alt") if portrait else "") or a.clean_text(),
                    slug=a.attrs["href"].rstrip("/").rsplit("/", 1)[-1],
                    icon=portrait.attrs.get("src", "") if portrait else "",
                    element=elem_img.attrs.get("alt", "") if elem_img else "",
                    rarity=_rarity(avatar) if avatar else 0,
                    sequence=seq.clean_text() if seq else "",
                    tags=[t for t in tags if t], mark=mark))
    if not entries:
        raise ValueError("Tier list is empty (Prydwen layout changed?)")
    return TierList(tiers=list(dict.fromkeys(tiers)), entries=entries, fetched=time.time())


def parse_character_list(html: str) -> dict[str, dict]:
    """Characters page -> {key(name): {name, slug, card, element, rarity}} (card = 280x400 portrait art)."""
    root = parse_html(html)
    out = {}
    for a in root.find_all("a", pred=lambda n: n.attrs.get("href", "").startswith("/wuthering-waves/characters/")):
        imgs = a.find_all("img")
        if not imgs:
            continue
        name = imgs[0].attrs.get("alt") or a.clean_text()
        avatar = a.find("div", "avatar")
        out[key(name)] = {"name": name, "slug": a.attrs["href"].rstrip("/").rsplit("/", 1)[-1],
                          "card": imgs[0].attrs.get("src", ""),
                          "element": imgs[1].attrs.get("alt", "") if len(imgs) > 1 else "",
                          "rarity": _rarity(avatar) if avatar else 0}
    if not out:
        raise ValueError("Character list is empty (Prydwen layout changed?)")
    return out


def _rewards(node: Node) -> list[dict]:
    out = []
    for r in node.find_all("span", "code-reward"):
        img = r.find("img")
        strong = r.find("strong")
        amount = strong.clean_text().lstrip("×x ").strip() if strong else ""
        name = r.clean_text()
        if strong:
            name = name.replace(strong.clean_text(), "").strip()
        out.append({"name": name, "amount": amount, "icon": img.attrs.get("src", "") if img else ""})
    return out


def parse_codes(html: str) -> dict:
    """Codes page -> {updated, active:[{code, rewards}], expired:[{code, rewards}]}."""
    root = parse_html(html)
    active, expired, seen = [], [], set()
    for card in root.find_all("article", "code-card"):
        c = card.find("code")
        if not c:
            continue
        code = c.clean_text()
        state = card.find("span", "code-state")
        is_exp = "is-expired" in card.classes or (state is not None and "expired" in state.clean_text().lower())
        (expired if is_exp else active).append({"code": code, "rewards": _rewards(card)})
        seen.add(code)
    for row in root.find_all("tr"):                      # 'all expired codes' table
        c = row.find("code")
        if c and c.clean_text() not in seen:
            expired.append({"code": c.clean_text(), "rewards": _rewards(row)})
            seen.add(c.clean_text())
    m = re.search(r"Updated\s+(\d{1,2}\s+\w+\s+\d{4})", root.clean_text())
    if not active and not expired:
        raise ValueError("No codes found on the page (Prydwen layout changed?)")
    return {"updated": m.group(1) if m else "", "active": active, "expired": expired}


def parse_character(html: str, slug: str) -> CharacterInfo:
    root = parse_html(html)
    info = CharacterInfo(name=slug, slug=slug, url=CHAR_URL.format(slug=slug), fetched=time.time())
    left = root.find("div", "left-info")
    if left:
        strong = left.find("strong")
        if strong:
            info.name = strong.clean_text()
            info.element = next(iter(strong.classes), "")
        m = re.search(r"Last updated:\s*(.+)", left.clean_text())
        if m:
            info.updated = m.group(1).strip()
    top = root.find("div", "character-top")
    if top:
        img = top.find("img")
        if img:
            info.card = img.attrs.get("src", "")
    # roles + ratings: <h5><span class="role dps"> DPS<span class="role-dupes"> [S0]</span></span></h5>
    #                  <div class="detailed-ratings ww"> rating boxes </div>
    for rd in root.find_all("div", "detailed-ratings"):
        ratings = {}
        for box in rd.find_all("div", "rating-box-container"):
            val = box.find("div", "rating-box")
            lab = box.find("p")
            if val and lab:
                ratings[lab.clean_text()] = val.clean_text()
        parent = rd.parent
        role_span = parent.find("span", pred=lambda n: "role" in n.classes and "role-dupes" not in n.classes) if parent else None
        role, seq = "", ""
        if role_span:
            dupes = role_span.find("span", "role-dupes")
            seq = dupes.clean_text().strip("[] ") if dupes else ""
            role = role_span.clean_text().replace(dupes.clean_text() if dupes else "", "").strip()
        if not ratings:
            continue
        if not role_span and info.roles:
            # a ratings block without its own role header belongs to the previous role
            info.roles[-1]["ratings"].update(ratings)
            continue
        same = next((r for r in info.roles if r["role"] == role and r["sequence"] == seq), None)
        if same:
            same["ratings"].update(ratings)       # e.g. the "(Value)" ratings of the same role
        else:
            info.roles.append({"role": role, "sequence": seq, "ratings": ratings})
    for acc in root.find_all("div", "ww-weapon-accordion"):
        for item in acc.find_all("div", "pw-accordion-item"):
            name_el = item.find("span", "ww-weapon-name")
            if not name_el:
                continue
            m = re.match(r"(.+?)\s*\(R\s*(\d)\)\s*$", name_el.clean_text())
            img = item.find("img")
            info.weapons.append({"name": m.group(1) if m else name_el.clean_text(),
                                 "refine": int(m.group(2)) if m else None, "rarity": _rarity(name_el),
                                 "icon": img.attrs.get("src", "") if img else ""})
    for acc in root.find_all("div", "ww-set-accordion"):
        for item in acc.find_all("div", "pw-accordion-item"):
            btn = item.find("button")
            if not btn:
                continue
            img = btn.find("img")
            name = btn.clean_text()
            if name and all(s["name"] != name for s in info.echo_sets):
                info.echo_sets.append({"name": name, "icon": img.attrs.get("src", "") if img else ""})
    # de-duplicate weapons (pages list them per build) keeping order
    uniq, out = set(), []
    for w in info.weapons:
        if (w["name"], w["refine"]) not in uniq:
            uniq.add((w["name"], w["refine"]))
            out.append(w)
    info.weapons = out
    return info


def parse_banners(html: str) -> list[dict]:
    """Banners page -> [{name, slug, category (character/weapon), section (current/upcoming), rerun, rarity,
    patch, phase, weapon_type, element, start/end per region (ISO, UTC) or "", featured, secondary, art}]"""
    root = parse_html(html)
    out = []
    for card in root.find_all("article", "banner-card"):
        name_el = card.find("p", "banner-name")
        if not name_el:
            continue
        timer = card.find("div", "art-timer")
        ta = timer.attrs if timer else {}
        times = {}
        for region in ("na", "eu", "asia"):
            times[region] = (ta.get(f"data-start-{region}", "") or "", ta.get(f"data-end-{region}", "") or "")
        meta = card.find("div", "banner-phase-meta")
        label = meta.find("span").clean_text() if meta and meta.find("span") else ""
        m = re.search(r"(\d+\.\d+)(?:\s*Phase\s*(\d+))?", label)
        chips = card.find_all("span", "icon-chip")
        wtype = next((c.clean_text() for c in chips if c.has_class("weapon")), "")
        elem = next((c.clean_text() for c in chips if c.has_class("element")), "")
        groups = {}
        for g in card.find_all("div", "featured-rate-ups"):
            lab = g.find("span", "featured-rate-ups-label")
            groups[lab.clean_text() if lab else ""] = [a.clean_text() for a in g.find_all("a", "featured-rate-up")]
        link = card.find("a", "banner-card-link")
        href = link.attrs.get("href", "") if link else ""
        imgs = [i for i in card.find_all("img") if i.attrs.get("alt")]
        rar = card.find("span", "rarity")
        btype = card.find("span", "banner-type")
        section = card.attrs.get("data-section", "")
        out.append({
            "name": name_el.clean_text(),
            "slug": href.rstrip("/").rsplit("/", 1)[-1] if "/characters/" in href else "",
            "category": card.attrs.get("data-category", "weapon" if card.has_class("weapon-banner-card") else "character"),
            "section": "current" if section == "current" else "upcoming",
            "rerun": bool(btype and btype.clean_text().lower() == "rerun"),
            "rarity": int(re.match(r"\d", rar.clean_text()).group()) if rar and re.match(r"\d", rar.clean_text()) else 5,
            "patch": m.group(1) if m else "", "phase": int(m.group(2)) if m and m.group(2) else None,
            "weapon_type": wtype, "element": elem,
            "times": times,
            "featured": groups.get("Featured Rate Up", []),
            "secondary": groups.get("Secondary Rate Up", []),
            "art": imgs[0].attrs.get("src", "") if imgs else "",
        })
    if not out:
        raise ValueError("No banners found on the page (Prydwen layout changed?)")
    return out


def banner_times(b: dict, region: str = "asia") -> tuple[str, str]:
    """(start, end) ISO strings for a server region, falling back to any region that has them."""
    t = b.get("times", {})
    for r in (region, "asia", "eu", "na"):
        s, e = t.get(r, ("", ""))
        if s or e:
            return s, e
    return "", ""


def parse_weapon_list(html: str) -> dict[str, dict]:
    """Weapons page -> {key(name): {name, rarity, type, icon, resource_id}}."""
    root = parse_html(html)
    out = {}
    for box in root.find_all("div", "ww-weapon-box"):
        h4 = box.find("h4")
        img = box.find("img")
        if not h4:
            continue
        name = h4.clean_text()
        rar = 0
        img_box = box.find("div", "ww-image")
        if img_box:
            for c in img_box.classes:
                mm = re.match(r"rar-(\d)", c)
                if mm:
                    rar = int(mm.group(1))
        wtype = ""
        for para in box.find_all("p"):
            txt = para.clean_text()
            if txt.startswith("Type:"):
                wtype = txt.split(":", 1)[1].strip()
        icon = img.attrs.get("src", "") if img else ""
        rid = re.search(r"/weapons/(\d+)\.", icon)
        out[key(name)] = {"name": name, "rarity": rar, "type": wtype, "icon": icon,
                          "resource_id": int(rid.group(1)) if rid else 0}
    if not out:
        raise ValueError("Weapon list is empty (Prydwen layout changed?)")
    return out


# ---------------------------------------------------------------- client with cache
class Prydwen:
    def __init__(self, cache_dir: Path, timeout: float = 20):
        self.dir = Path(cache_dir)
        (self.dir / "img").mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    # --- http
    def _get(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read()

    def _cached_json(self, name: str, ttl: float, fetch, force: bool):
        path = self.dir / f"{name}.json"
        if path.exists() and not force:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("fetched", 0) < ttl:
                return data, True
        try:
            data = fetch()
        except Exception:
            if path.exists():  # offline / site down: use stale cache
                return json.loads(path.read_text(encoding="utf-8")), True
            raise
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data, False

    # --- public API
    def tier_list(self, force: bool = False) -> TierList:
        def fetch():
            return asdict(parse_tier_list(self._get(TIER_URL).decode("utf-8", "replace")))
        data, _ = self._cached_json("tierlist", TTL_TIER, fetch, force)
        tl = TierList(tiers=data["tiers"], entries=[TierEntry(**e) for e in data["entries"]],
                      fetched=data.get("fetched", 0), mode=data.get("mode", "Tower of Adversity"))
        try:
            self._record_tier_snapshot(tl)
        except (OSError, ValueError):
            pass
        return tl

    def character(self, slug: str, force: bool = False) -> CharacterInfo:
        slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
        def fetch():
            return asdict(parse_character(self._get(CHAR_URL.format(slug=slug)).decode("utf-8", "replace"), slug))
        data, _ = self._cached_json(f"char_{slug}", TTL_CHAR, fetch, force)
        return CharacterInfo(**data)

    def character_list(self, force: bool = False) -> dict[str, dict]:
        def fetch():
            return {"fetched": time.time(),
                    "chars": parse_character_list(self._get(CHARS_URL).decode("utf-8", "replace"))}
        data, _ = self._cached_json("characters", TTL_CHAR, fetch, force)
        return data["chars"]

    def codes(self, force: bool = False) -> dict:
        def fetch():
            d = parse_codes(self._get(CODES_URL).decode("utf-8", "replace"))
            d["fetched"] = time.time()
            return d
        data, _ = self._cached_json("codes", TTL_CODES, fetch, force)
        return data

    def banners(self, force: bool = False) -> list[dict]:
        def fetch():
            return {"fetched": time.time(),
                    "banners": parse_banners(self._get(BANNERS_URL).decode("utf-8", "replace"))}
        data, _ = self._cached_json("banners", TTL_BANNERS, fetch, force)
        self._record_banner_history(data["banners"])
        return data["banners"]

    def cached_banners(self) -> list[dict]:
        path = self.dir / "banners.json"
        return json.loads(path.read_text(encoding="utf-8")).get("banners", []) if path.exists() else []

    def weapon_list(self, force: bool = False) -> dict[str, dict]:
        def fetch():
            return {"fetched": time.time(),
                    "weapons": parse_weapon_list(self._get(WEAPONS_URL).decode("utf-8", "replace"))}
        data, _ = self._cached_json("weapons", TTL_WEAPONS, fetch, force)
        return data["weapons"]

    def cached_weapon_list(self) -> dict[str, dict]:
        path = self.dir / "weapons.json"
        return json.loads(path.read_text(encoding="utf-8")).get("weapons", {}) if path.exists() else {}

    # --- history kept locally (Prydwen only shows the present)
    def _record_banner_history(self, banners: list[dict]) -> None:
        """Every banner ever seen on Prydwen's page, kept in banner_history.json (for the rerun tracker)."""
        path = self.dir / "banner_history.json"
        hist = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        changed = False
        for b in banners:
            s, e = banner_times(b)
            if not s:
                continue
            k = f"{b['category']}|{b['name']}|{s[:10]}"
            if k not in hist:
                hist[k] = {"name": b["name"], "category": b["category"], "patch": b["patch"], "phase": b["phase"],
                           "start": s[:10], "end": e[:10], "rerun": b["rerun"], "featured": b["featured"]}
                changed = True
        if changed:
            path.write_text(json.dumps(hist, indent=1, ensure_ascii=False), encoding="utf-8")

    def banner_history(self) -> list[dict]:
        path = self.dir / "banner_history.json"
        return list(json.loads(path.read_text(encoding="utf-8")).values()) if path.exists() else []

    def _record_tier_snapshot(self, tl: "TierList") -> None:
        """One snapshot per day when the tier list changed: {date: {name: tier}}."""
        path = self.dir / "tier_history.json"
        hist = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        snap = {}
        for e in tl.entries:
            snap.setdefault(e.name, e.tier)
        if hist and hist[max(hist)] == snap:
            return
        hist[time.strftime("%Y-%m-%d", time.localtime(tl.fetched or time.time()))] = snap
        path.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    def tier_history(self, name: str | None = None) -> dict:
        """{date: {name: tier}}, or for one character {date: tier} (only dates where it was listed)."""
        path = self.dir / "tier_history.json"
        hist = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if name is None:
            return hist
        k = key(name)
        out = {}
        for d in sorted(hist):
            for n, tier in hist[d].items():
                if key(n) == k:
                    out[d] = tier
        return out

    def cached_character_list(self) -> dict[str, dict]:
        path = self.dir / "characters.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8")).get("chars", {})

    def card_url(self, name: str, resource_id: int | None = None) -> str | None:
        """Large portrait art for banner cards: character card art, weapon icon, or tier-list icon."""
        if resource_id and resource_id >= WEAPON_ID_MIN:
            return WEAPON_ICON.format(rid=resource_id)
        c = self.cached_character_list().get(key(name))
        if c and c.get("card"):
            return c["card"]
        return self.portrait_url(name)

    def cached_tier_list(self) -> TierList | None:
        path = self.dir / "tierlist.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return TierList(tiers=data["tiers"], entries=[TierEntry(**e) for e in data["entries"]],
                        fetched=data.get("fetched", 0))

    def image_path(self, url: str) -> Path | None:
        """Local path of an image if it is already cached (never downloads)."""
        if not url:
            return None
        ext = Path(url.split("?")[0]).suffix or ".img"
        path = self.dir / "img" / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
        return path if path.exists() and path.stat().st_size > 0 else None

    def image(self, url: str) -> Path | None:
        """Download (once) and return the local path of an image."""
        if not url:
            return None
        ext = Path(url.split("?")[0]).suffix or ".img"
        path = self.dir / "img" / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
        if path.exists() and path.stat().st_size > 0:
            return path
        try:
            path.write_bytes(self._get(url))
            return path
        except Exception:
            return None

    def find_slug(self, name: str) -> str | None:
        tl = self.cached_tier_list()
        if tl:
            e = tl.by_key().get(key(name))
            if e:
                return e.slug
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or None

    def portrait_url(self, name: str, resource_id: int | None = None) -> str | None:
        """Icon URL for a pulled item: weapons by resourceId, characters via the tier list."""
        if resource_id and resource_id >= WEAPON_ID_MIN:
            return WEAPON_ICON.format(rid=resource_id)
        w = self.cached_weapon_list().get(key(name)) if not resource_id else None
        if w and w.get("icon"):
            return w["icon"]
        tl = self.cached_tier_list()
        if tl:
            e = tl.by_key().get(key(name))
            if e and e.icon:
                return e.icon
        return None
