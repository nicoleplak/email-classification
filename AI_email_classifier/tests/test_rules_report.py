"""docs/decision_rules.html (what the business reviews) must match the rule files the code runs on."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_decision_rules_page_is_up_to_date():
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "rules_report.py"), "--check"],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr or done.stdout
