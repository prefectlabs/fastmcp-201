"""One smoke test per act: run demo.py as an attendee would, from an empty environment.

These start real servers on port 8201 and call Open-Meteo. Skip them with
``pytest -m "not lab"``.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLEAN_ENV = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]}

EXPECTED = {
    "1": [
        "HTTP 401",
        ">> Read-only token: the catalog",
        "tool error: Unknown tool: 'save_favorite_location'",
        "new: ['save_favorite_location']",
        "Saved 'Denver' for [redacted].",
        "Checkpoint: the tool list changed",
    ],
    "2": [
        "Saved 'Denver' for [redacted].",
        "event=request_start method=tools/call",
        "event=request_success method=tools/call",
        "method=tools/list",
        "Checkpoint: one line per call",
    ],
    "3": [
        ">> Receipt, back at once",
        "status=working",
        "fetching 2025-11-01 (1 of 4)",
        '"rain_probability_pct"',
        "Which date do you mean for Denver?",
        "Rain outlook for Denver",
        "No date chosen (decline).",
        "Checkpoint: the agent got a receipt",
    ],
    "4": [
        "search_tools\n   call_tool",
        "rain_check",
        "search\n   get_schema\n   execute",
        '"outlook"',
        "Checkpoint: twenty tools, two in context.",
    ],
    "proxy": [
        "save_favorite_location",
        "Saved 'Denver' for [redacted].",
        "Checkpoint: the agent never held the credential",
    ],
}


ALPHA = ROOT / ".venv-skills" / "bin" / "python"


@pytest.mark.lab
@pytest.mark.skipif(not ALPHA.exists(), reason="no .venv-skills (FastMCP 4.2.0a1) on this machine")
def test_skill_demo_runs_on_the_alpha():
    proc = subprocess.run([str(ALPHA), str(ROOT / "demo.py"), "skill"], cwd=ROOT, env=CLEAN_ENV, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "name: rain-outlook" in proc.stdout
    assert "Checkpoint: the methodology ships as a skill" in proc.stdout


@pytest.mark.lab
@pytest.mark.parametrize("act", list(EXPECTED))
def test_demo_runs_clean(act):
    proc = subprocess.run([sys.executable, str(ROOT / "demo.py"), act], cwd=ROOT, env=CLEAN_ENV, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    for needle in EXPECTED[act]:
        assert needle in proc.stdout, f"missing {needle!r} in:\n{proc.stdout}"
