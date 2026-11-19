"""Browser test for the multi-user review server, on invented emails only.

    python evaluation/browser_test/run_server.py
    python evaluation/browser_test/run_server.py --real   # every imported email, counts only

Starts review_server.py on a temporary database, then runs server_test.cjs with
Playwright's bundled Chromium: two reviewers at once, presence, saving, conflicts,
the activity feed, loading states and layout at several sizes. Prints numbers and
short labels only; screenshots go to runs/eval/ui_test_output/ for a person to look at.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parents[2] / "runs" / "eval" / "ui_test_output"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE.parent))
    sys.path.insert(0, str(HERE))
    real = "--real" in sys.argv
    with tempfile.TemporaryDirectory() as folder:
        # --real walks the imported review.db read-only and reports counts; never screenshots.
        db = OUT_DIR.parent / "review.db" if real else Path(folder) / "review.db"
        env = {**os.environ, "REVIEW_DB": str(db), "REVIEW_AUTH": "dev"}
        if not real:
            import review_server
            import synthetic

            review_server.DB_PATH = db
            review_server.load_emails(synthetic.payload(60), "browser-test")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = subprocess.Popen([sys.executable, str(HERE.parent / "review_server.py"), "serve", str(port)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}/"
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(base, timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.2)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            command = ["node", str(HERE / "server_test.cjs"), base, str(OUT_DIR)] + (["real"] if real else [])
            return subprocess.run(command, check=False).returncode
        finally:
            server.terminate()
            errors = server.communicate(timeout=10)[1].decode("utf-8", "replace").strip()
            if errors:
                print("server stderr:", errors[-800:])


if __name__ == "__main__":
    sys.exit(main())
