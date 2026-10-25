"""Start all four local processes with one command (Ctrl+C stops them all):

    python scripts/dev.py

  api        Django REST API            http://127.0.0.1:8000
  worker     message delivery worker
  simulator  SimuText provider          http://127.0.0.1:8001
  web        Next.js frontend           http://localhost:3000
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin")
PYTHON = BIN / ("python.exe" if os.name == "nt" else "python")


def main() -> None:
    if not PYTHON.exists():
        sys.exit("No virtual environment found. Run 'python scripts/setup_dev.py' first.")
    env = os.environ.copy()
    # Make plain `python` in Procfile.dev resolve to the project's virtualenv.
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"  # Windows consoles otherwise choke on non-ASCII log output
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        subprocess.run([str(PYTHON), "-m", "honcho", "-f", "Procfile.dev", "start"], cwd=ROOT, env=env, check=False)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
