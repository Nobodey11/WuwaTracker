"""Check that the Prydwen parsers still understand Prydwen's live pages (run weekly by GitHub Actions).

    python tools/prydwen_check.py          exit code 1 + a report when a page can't be parsed any more
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wuwa_tracker.core import prydwen as pw  # noqa: E402


def main() -> int:
    p = pw.Prydwen(Path(tempfile.mkdtemp()))
    checks = {
        "tier list": lambda: f"{len(p.tier_list(True).entries)} entries",
        "character list": lambda: f"{len(p.character_list(True))} characters",
        "character page (hsin)": lambda: f"{len(p.character('hsin', True).roles)} role ratings",
        "codes": lambda: f"{len(p.codes(True)['active'])} active codes",
        "banners": lambda: f"{len(p.banners(True))} banners",
        "weapon list": lambda: f"{len(p.weapon_list(True))} weapons",
    }
    failed = 0
    for name, fn in checks.items():
        try:
            print(f"OK    {name}: {fn()}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    if failed:
        print(f"\n{failed} Prydwen page(s) changed layout: update the parser in wuwa_tracker/core/prydwen.py "
              "(and the matching test fixture).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
