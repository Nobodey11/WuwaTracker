"""Ollama model benchmark: ask every model the same probability questions about YOUR data and score them.

For each question the correct answer is computed first by the exact engine (through the same tool the model may
call). A model scores when a number in its answer is within the tolerance of the correct value. We also record
whether it called the right tool and how long it took. Nice for comparing tool-calling reliability of local models.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

NUM = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)")


@dataclass
class Question:
    text: str
    tool: str
    expected: float
    tolerance: float          # absolute, same unit as expected
    unit: str = "%"


@dataclass
class Score:
    model: str
    question: str
    correct: bool
    used_tool: bool
    seconds: float
    answer: str
    expected: float
    error: str = ""


@dataclass
class ModelScore:
    model: str
    scores: list[Score] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return sum(s.correct for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def tool_rate(self) -> float:
        return sum(s.used_tool for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def avg_seconds(self) -> float:
        return sum(s.seconds for s in self.scores) / len(self.scores) if self.scores else 0.0


def numbers(text: str) -> list[float]:
    out = []
    for m in NUM.findall(text or ""):
        s = m
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):        # thousands separators: 1,311 / 9.600
            s = re.sub(r"[.,]", "", s)
        else:
            s = s.replace(",", ".")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def build_questions(toolbox) -> list[Question]:
    """Questions whose right answers come from the engine on the user's current data."""
    qs = []
    have_char = toolbox._banner(1) is not None
    pt = 1 if have_char else 2
    r = toolbox.t_featured_probability(pt, 40)
    qs.append(Question("What is my chance to get the featured 5★ within 40 pulls on the "
                       f"{'character' if pt == 1 else 'weapon'} banner? Give the percentage.",
                       "featured_probability", r["probability_percent"], 1.0))
    r = toolbox.t_featured_probability(pt, 120, copies=2)
    qs.append(Question("What's the chance of getting 2 copies of the featured 5★ in 120 pulls from my current state?",
                       "featured_probability", r["probability_percent"], 1.0))
    r = toolbox.t_pulls_needed(pt, 1, 0.9)
    qs.append(Question("How many pulls do I need for a 90 % chance at the featured 5★?", "pulls_needed",
                       r["pulls_for_90pct"], 1, "pulls"))
    r = toolbox.t_next_pulls(pt)
    qs.append(Question("What is the chance that my very next single pull is a 5★?", "next_pulls",
                       r["next_1_pull"]["any5"], 0.05))
    r = toolbox.t_astrite_to_pulls(9600, 12)
    qs.append(Question("I have 9,600 Astrite and 12 Radiant Tides. How many pulls is that?", "astrite_to_pulls",
                       r["pulls"], 0, "pulls"))
    ov = toolbox.t_get_overview()["banners"]
    if ov:
        b = next((x for x in ov if x["pool_type"] == pt), ov[0])
        qs.append(Question(f"What is my current 5★ pity on the {b['banner']} banner?", "get_overview",
                           b["current_5star_pity"], 0, "pulls"))
    return qs


def score_answer(answer: str, q: Question) -> bool:
    return any(abs(n - q.expected) <= q.tolerance + 1e-9 for n in numbers(answer))


def run(client, models: list[str], toolbox, questions: list[Question] | None = None, system: str | None = None,
        progress=lambda text: None, stop=lambda: False) -> list[ModelScore]:
    from .ollama_client import SYSTEM_PROMPT
    questions = questions or build_questions(toolbox)
    results = []
    for m in models:
        ms = ModelScore(m)
        for i, q in enumerate(questions, 1):
            if stop():
                return results + [ms]
            progress(f"{m}: question {i}/{len(questions)}")
            used = []
            t0 = time.time()
            try:
                ans, _ = client.chat(m, [{"role": "system", "content": system or SYSTEM_PROMPT},
                                         {"role": "user", "content": q.text}], toolbox,
                                     on_tool=lambda n, a, r: used.append(n), temperature=0.0)
                err = ""
            except Exception as e:
                ans, err = "", str(e)
            ms.scores.append(Score(m, q.text, score_answer(ans, q), q.tool in used, time.time() - t0, ans,
                                   q.expected, err))
        results.append(ms)
    return results


def report(results: list[ModelScore]) -> str:
    lines = ["| Model | Correct | Used the right tool | Avg. time |", "|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (-r.accuracy, -r.tool_rate, r.avg_seconds)):
        lines.append(f"| {r.model} | {r.accuracy:.0%} | {r.tool_rate:.0%} | {r.avg_seconds:.1f} s |")
    return "\n".join(lines)
