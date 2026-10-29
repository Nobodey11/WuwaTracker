"""Test-run housekeeping.

On Windows, Qt can crash while the interpreter shuts down after the tests (threads/objects torn down in the wrong
order), which turns a fully green run into exit code 1 on GitHub Actions. After pytest has reported, leave with
pytest's own exit status instead.
"""
import os
import sys


def pytest_sessionfinish(session, exitstatus):
    session.config._wuwa_exit = int(exitstatus)


def pytest_unconfigure(config):
    if "PySide6.QtCore" in sys.modules and hasattr(config, "_wuwa_exit"):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(config._wuwa_exit)
