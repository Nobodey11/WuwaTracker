"""Minimal Ollama client with tool calling. No external dependencies (urllib only).

The LLM is never trusted to do the maths: it calls the tools below, which run the exact
probability engine on your real data.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from . import probability as pr
from .models import ASTRITE_PER_PULL, BannerStats

SYSTEM_PROMPT = """You are a friendly Wuthering Waves Convene (gacha) analyst inside a desktop pull tracker.
Rules:
- NEVER calculate probabilities yourself. Always call the tools; they run an exact model on the user's real pull data.
- Use get_overview first if you don't know which banners exist or what the current pity is.
- Use get_banner_schedule for questions about current/upcoming banners or patches.
- 1 pull = 160 Astrite. Character banner: 50/50 on the first 5★, guaranteed after a loss. Weapon banner: 5★ is always the featured weapon. Hard pity 80.
- The soft-pity curve after pull 66 is a community estimate, not official; say so when it matters.
- Answer concisely, with the key numbers in bold. Answer in the user's language (Dutch or English)."""

TOOLS = [
    {"type": "function", "function": {
        "name": "get_overview",
        "description": "Summary of every banner: total pulls, current 5★/4★ pity, guarantee status, 5★ count, 50/50 record.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_banner_details",
        "description": "Full 5★ history (name, pity, date, 50/50 result) for one banner.",
        "parameters": {"type": "object", "properties": {
            "pool_type": {"type": "integer", "description": "1=Featured Resonator, 2=Featured Weapon, 3=Standard Resonator, 4=Standard Weapon, 12=Reverb..."}},
            "required": ["pool_type"]}}},
    {"type": "function", "function": {
        "name": "featured_probability",
        "description": "Exact chance of getting at least `copies` featured 5★ within `pulls` pulls, starting from the user's current pity and guarantee on that banner (or overrides).",
        "parameters": {"type": "object", "properties": {
            "pool_type": {"type": "integer", "description": "1 = character banner, 2 = weapon banner"},
            "pulls": {"type": "integer"},
            "copies": {"type": "integer", "description": "default 1"},
            "pity": {"type": "integer", "description": "optional override of current pity"},
            "guaranteed": {"type": "boolean", "description": "optional override of guarantee"}},
            "required": ["pool_type", "pulls"]}}},
    {"type": "function", "function": {
        "name": "pulls_needed",
        "description": "How many pulls (and Astrite) are needed to get `copies` featured 5★ with a given confidence, from the current state. Also returns the expected (average) number of pulls.",
        "parameters": {"type": "object", "properties": {
            "pool_type": {"type": "integer"},
            "copies": {"type": "integer"},
            "confidence": {"type": "number", "description": "0-1, e.g. 0.5, 0.9"}},
            "required": ["pool_type", "copies"]}}},
    {"type": "function", "function": {
        "name": "get_banner_schedule",
        "description": "Current and upcoming banners from the game data (patch, phase, dates, featured 5★/4★), plus the game-data version.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "astrite_to_pulls",
        "description": "Convert Astrite (and optional Radiant/Forging Tides already owned) into number of pulls.",
        "parameters": {"type": "object", "properties": {
            "astrite": {"type": "integer"}, "tides": {"type": "integer"}}, "required": ["astrite"]}}},
]


class ToolBox:
    """Executes tool calls against the app's current data."""

    def __init__(self, stats_provider: Callable[[], dict[int, BannerStats]], hazard_provider: Callable[[], object],
                 gamedata_provider: Callable[[], object] | None = None):
        self.stats = stats_provider
        self.hazard = hazard_provider
        self.gamedata = gamedata_provider

    def _banner(self, pool_type: int) -> BannerStats | None:
        return self.stats().get(int(pool_type))

    def run(self, name: str, args: dict) -> dict:
        try:
            return getattr(self, "t_" + name)(**(args or {}))
        except Exception as e:  # report errors back to the model instead of crashing
            return {"error": f"{type(e).__name__}: {e}"}

    def t_get_overview(self):
        out = []
        for s in self.stats().values():
            d = s.to_dict()
            d.pop("five_stars")
            out.append(d)
        return {"banners": out}

    def t_get_banner_details(self, pool_type):
        s = self._banner(pool_type)
        return s.to_dict() if s else {"error": f"no pulls for pool_type {pool_type}"}

    def _state(self, pool_type, pity=None, guaranteed=None):
        s = self._banner(pool_type)
        p = pity if pity is not None else (s.pity5 if s else 0)
        g = guaranteed if guaranteed is not None else (s.guaranteed if s else False)
        fc = s.featured_chance if s and s.featured_chance is not None else (0.5 if int(pool_type) == 1 else 1.0)
        return int(p), bool(g), fc

    def t_featured_probability(self, pool_type, pulls, copies=1, pity=None, guaranteed=None):
        p, g, fc = self._state(pool_type, pity, guaranteed)
        r = pr.featured_distribution(self.hazard(), int(pulls), int(copies), p, g, fc)
        return {"pool_type": pool_type, "start_pity": p, "guaranteed": g, "pulls": int(pulls),
                "astrite": r.astrite, "copies": int(copies),
                "probability_percent": round(r.probability * 100, 2),
                "expected_featured_copies": round(r.expected_featured, 2)}

    def t_pulls_needed(self, pool_type, copies=1, confidence=0.9):
        p, g, fc = self._state(pool_type)
        h = self.hazard()
        out = {"pool_type": pool_type, "start_pity": p, "guaranteed": g, "copies": int(copies),
               "expected_pulls": round(pr.expected_pulls_featured(h, int(copies), p, g, fc), 1)}
        for c in sorted({0.5, 0.9, float(confidence)}):
            n = pr.pulls_needed(h, int(copies), c, p, g, fc)
            out[f"pulls_for_{int(c * 100)}pct"] = n
            out[f"astrite_for_{int(c * 100)}pct"] = n * ASTRITE_PER_PULL
        return out

    def t_get_banner_schedule(self):
        if not self.gamedata:
            return {"error": "no game data available"}
        gd = self.gamedata()
        return {"game_data_version": gd.version, "game_patch": gd.patch, "today": __import__("datetime").date.today().isoformat(),
                "current": gd.current_banners(), "upcoming": gd.upcoming_banners()}

    def t_astrite_to_pulls(self, astrite, tides=0):
        return {"pulls": int(astrite) // ASTRITE_PER_PULL + int(tides or 0),
                "leftover_astrite": int(astrite) % ASTRITE_PER_PULL}


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", timeout: float = 300):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(self.host + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise OllamaError(e.read().decode(errors="replace") or str(e)) from e
        except urllib.error.URLError as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host} — is it running? ({e.reason})") from e

    def list_models(self) -> list[str]:
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=5) as r:
                return sorted(m["name"] for m in json.loads(r.read()).get("models", []))
        except Exception as e:
            raise OllamaError(f"Cannot reach Ollama at {self.host}: {e}") from e

    def chat(self, model: str, messages: list[dict], toolbox: ToolBox | None = None,
             on_tool: Callable[[str, dict, dict], None] | None = None, max_rounds: int = 6,
             temperature: float = 0.3) -> tuple[str, list[dict]]:
        """Run a full chat turn, executing tool calls until the model answers.
        Returns (answer, updated_messages). Falls back to context injection if the
        model does not support tools."""
        msgs = list(messages)
        use_tools = toolbox is not None
        for _ in range(max_rounds):
            payload = {"model": model, "messages": msgs, "stream": False,
                       "options": {"temperature": temperature}}
            if use_tools:
                payload["tools"] = TOOLS
            try:
                resp = self._post("/api/chat", payload)
            except OllamaError as e:
                if use_tools and "does not support tools" in str(e):
                    use_tools = False
                    msgs = _inject_context(msgs, toolbox)
                    continue
                raise
            msg = resp.get("message", {})
            msgs.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content", "").strip(), msgs
            for c in calls:
                fn = c.get("function", {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = toolbox.run(name, args)
                if on_tool:
                    on_tool(name, args, result)
                msgs.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})
        return "(Stopped: too many tool calls.)", msgs


def _inject_context(msgs: list[dict], toolbox: ToolBox) -> list[dict]:
    """For models without tool support: put pre-computed facts in the system prompt."""
    facts = {"overview": toolbox.t_get_overview(), "schedule": toolbox.t_get_banner_schedule()}
    for pt in (1, 2):
        if toolbox._banner(pt):
            facts[f"pool_{pt}_odds"] = {
                f"{n}_pulls": toolbox.t_featured_probability(pt, n)["probability_percent"] for n in (10, 20, 40, 60, 80, 120, 160)}
            facts[f"pool_{pt}_needed"] = toolbox.t_pulls_needed(pt, 1)
    extra = ("\n\nYour model has no tool support, so here are pre-computed facts (JSON). "
             "Only quote these numbers; say you can't compute other scenarios:\n" + json.dumps(facts))
    out = [m for m in msgs if m.get("role") != "tool" and not m.get("tool_calls")]
    if out and out[0].get("role") == "system":
        out[0] = {"role": "system", "content": out[0]["content"] + extra}
    else:
        out.insert(0, {"role": "system", "content": SYSTEM_PROMPT + extra})
    return out
