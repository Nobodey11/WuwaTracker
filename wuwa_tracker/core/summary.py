"""Weekly pull summary ("pull-log narrator"): facts are computed here; Ollama may only rephrase them."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from .models import ASTRITE_PER_PULL


def week_facts(pulls, stats, gd, now: datetime | None = None, days: int = 7) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    recent = sorted((p for p in pulls if p.time >= start), key=lambda p: (p.time, p.group))
    by_banner = Counter(p.pool_type for p in recent)
    fives = []
    pity = Counter()
    for p in sorted(pulls, key=lambda p: (p.pool_type, p.time, p.group)):
        pity[p.pool_type] += 1
        if p.quality == 5:
            if p.time >= start:
                res = ""
                st = stats.get(p.pool_type)
                if st:
                    ev = next((f for f in st.five_stars if f.time == p.time and f.name == p.name), None)
                    res = ev.result if ev else ""
                fives.append({"name": p.name, "pity": pity[p.pool_type], "banner": gd.name(p.pool_type),
                              "date": p.time.date().isoformat(), "result": res})
            pity[p.pool_type] = 0
    fours = sorted({p.name for p in recent if p.quality == 4})
    current = []
    for pt in gd.featured_pools():
        s = stats.get(pt)
        if s:
            current.append({"banner": s.name, "pity": s.pity5,
                            "guaranteed": s.guaranteed if s.has_5050 else None})
    return {"from": start.date().isoformat(), "to": now.date().isoformat(), "pulls": len(recent),
            "astrite": len(recent) * ASTRITE_PER_PULL,
            "per_banner": {gd.name(pt): n for pt, n in sorted(by_banner.items())},
            "five_stars": fives, "four_star_names": fours, "four_star_count": sum(1 for p in recent if p.quality == 4),
            "pity_now": current}


def week_text(f: dict) -> str:
    if not f["pulls"]:
        lines = [f"No pulls between {f['from']} and {f['to']}. Saving up? 💰"]
    else:
        lines = [f"This week ({f['from']} → {f['to']}): **{f['pulls']:,} pulls**, {f['astrite']:,} Astrite."]
        if f["per_banner"]:
            lines.append("Banners: " + ", ".join(f"{b} {n}" for b, n in f["per_banner"].items()) + ".")
        if f["five_stars"]:
            for x in f["five_stars"]:
                tag = {"won": " (won the 50/50 🎉)", "lost": " (lost the 50/50, next is guaranteed)",
                       "guaranteed": " (guaranteed)"}.get(x["result"], "")
                lines.append(f"★5 **{x['name']}** at pity {x['pity']} on {x['banner']}{tag}.")
        else:
            lines.append("No 5★ this week.")
        if f["four_star_count"]:
            lines.append(f"{f['four_star_count']} × 4★" + (": " + ", ".join(f["four_star_names"][:8]) if f["four_star_names"] else "") + ".")
    for c in f["pity_now"]:
        g = " · next 5★ guaranteed" if c["guaranteed"] else ""
        lines.append(f"Now: {c['banner']} at pity {c['pity']}{g}.")
    return "\n\n".join(lines)


def week_prompt(f: dict, persona: str = "") -> list[dict]:
    import json
    sys = ("Write a short, fun weekly recap (max 6 sentences) of the user's Wuthering Waves pulls. Use ONLY the facts "
           "in the JSON; never invent numbers. Bold the key numbers. " + persona)
    return [{"role": "system", "content": sys}, {"role": "user", "content": json.dumps(f)}]
