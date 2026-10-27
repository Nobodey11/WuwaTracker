"""Print the CHANGELOG section of a version (used for the GitHub release text).   python tools/release_notes.py 1.0.0"""
import re
import sys
from pathlib import Path

ver = sys.argv[1].lstrip("v")
text = Path(__file__).resolve().parents[1].joinpath("CHANGELOG.md").read_text(encoding="utf-8")
parts = re.split(r"(?m)^## ", text)
sec = next((p for p in parts if p.startswith(ver + " ")), None)
body = ("## " + sec.strip()) if sec else f"WuWa Pull Tracker {ver}"
print(body + "\n\n**Download:** WuwaTracker-" + ver + "-windows.zip below → unzip → run WuwaTracker.exe "
      "(no Python needed). Unofficial fan tool, for personal use only.")
