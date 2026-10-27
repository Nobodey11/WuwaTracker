"""Small local knowledge search for the AI assistant (retrieval-augmented generation).

Documents:
  * your own notes: *.md / *.txt files in the notes folder (data folder/notes)
  * cached Prydwen character guides (ratings, best weapons, echo sets) and the tier list
  * the game data (banners, standard/limited lists)
Ranking: BM25 over word tokens, pure Python (no embedding model needed).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9★]+")
STOP = set("the a an and or of to in on for is are was it this that with be as at by from you your i my me".split())


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


@dataclass
class Doc:
    title: str
    source: str
    text: str


class Index:
    def __init__(self, docs: list[Doc], k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens(d.title + " " + d.title + " " + d.text)) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1.0
        df = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[float, Doc]]:
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scores.append((s, self.docs[i]))
        return sorted(scores, key=lambda x: -x[0])[:k]


def _chunks(text: str, size: int = 900) -> list[str]:
    paras, out, cur = re.split(r"\n\s*\n", text), [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            out.append(cur.strip()); cur = ""
        cur += p + "\n\n"
    if cur.strip():
        out.append(cur.strip())
    return out


def collect(notes_dir: Path | None, prydwen_dir: Path | None, gd_raw: dict | None) -> list[Doc]:
    docs: list[Doc] = []
    if notes_dir and Path(notes_dir).is_dir():
        for f in sorted(Path(notes_dir).rglob("*")):
            if f.suffix.lower() in (".md", ".txt") and f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for i, c in enumerate(_chunks(text)):
                    docs.append(Doc(f.stem + (f" ({i + 1})" if i else ""), f"note: {f.name}", c))
    if prydwen_dir and Path(prydwen_dir).is_dir():
        for f in sorted(Path(prydwen_dir).glob("char_*.json")):
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            parts = [f"{c['name']} ({c.get('element', '')}, {c.get('rarity', '')}★)."]
            for r in c.get("roles", []):
                parts.append(f"Role {r.get('role')}: " + ", ".join(f"{k} {v}" for k, v in r.get("ratings", {}).items()))
            if c.get("weapons"):
                parts.append("Best weapons: " + ", ".join(w["name"] for w in c["weapons"][:6]) + ".")
            if c.get("echo_sets"):
                parts.append("Echo sets: " + ", ".join(s["name"] for s in c["echo_sets"][:4]) + ".")
            docs.append(Doc(c["name"], f"Prydwen guide ({c.get('url', '')})", " ".join(parts)))
        tl = Path(prydwen_dir) / "tierlist.json"
        if tl.exists():
            try:
                d = json.loads(tl.read_text(encoding="utf-8"))
                by = {}
                for e in d.get("entries", []):
                    by.setdefault(e["tier"], []).append(e["name"])
                docs.append(Doc("Prydwen tier list", "Prydwen tier list",
                                " ".join(f"Tier {t}: {', '.join(ns)}." for t, ns in by.items())))
            except (OSError, json.JSONDecodeError, KeyError):
                pass
    if gd_raw:
        for b in gd_raw.get("banners", []):
            docs.append(Doc(f"Banner {b['patch']} phase {b.get('phase')}", "game data",
                            f"Patch {b['patch']} phase {b.get('phase')} from {b['start']} to {b['end']}: 5★ "
                            + ", ".join(b.get("featured_5star_resonators", [])) + "; weapons "
                            + ", ".join(b.get("featured_5star_weapons", [])) + "; 4★ "
                            + ", ".join(b.get("featured_4star_resonators", [])) + "."))
        docs.append(Doc("Standard 5★ pool", "game data",
                        "Standard (lose the 50/50 to) resonators: " + ", ".join(gd_raw.get("standard_5star_resonators", []))
                        + ". Limited resonators: " + ", ".join(gd_raw.get("limited_5star_resonators", [])) + "."))
    return docs


def search(query: str, notes_dir=None, prydwen_dir=None, gd_raw=None, k: int = 4) -> list[dict]:
    idx = Index(collect(notes_dir, prydwen_dir, gd_raw))
    return [{"title": d.title, "source": d.source, "text": d.text[:1200], "score": round(s, 2)}
            for s, d in idx.search(query, k)]
