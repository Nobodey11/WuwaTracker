"""Benchmark local Ollama models on probability questions about your own pulls (command-line version).

    python tools/benchmark.py                       all installed models, your database
    python tools/benchmark.py qwen2.5:7b llama3.1:8b --host http://localhost:11434
Writes a Markdown report to benchmark_report.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wuwa_tracker.core import benchmark, probability as pr  # noqa: E402
from wuwa_tracker.core.analysis import all_stats  # noqa: E402
from wuwa_tracker.core.gamedata import GameDataStore  # noqa: E402
from wuwa_tracker.core.ollama_client import OllamaClient, ToolBox  # noqa: E402
from wuwa_tracker.core.storage import Storage  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--db")
    a = ap.parse_args()
    st = Storage(a.db)
    player = st.get_setting("player") or (st.players() or [""])[0]
    gd = GameDataStore(st.path.parent).load()
    stats = all_stats(st.load(player or None), gd)
    tb = ToolBox(lambda: stats, lambda: pr.hazard_community(gd.rates), lambda: gd)
    client = OllamaClient(a.host, timeout=180)
    models = a.models or client.list_models()
    res = benchmark.run(client, models, tb, progress=print)
    rep = benchmark.report(res)
    print("\n" + rep)
    Path("benchmark_report.md").write_text("# Ollama benchmark\n\n" + rep + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
