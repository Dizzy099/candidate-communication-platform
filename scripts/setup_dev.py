"""One-time local setup. Run from the repository root:

    python scripts/setup_dev.py

Creates the Python virtual environment, installs dependencies, writes local
.env files with freshly generated shared secrets, creates both databases,
loads demo data and installs the frontend packages. Safe to run again.
"""

import os
import secrets
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
BIN = VENV / ("Scripts" if os.name == "nt" else "bin")
PYTHON = BIN / ("python.exe" if os.name == "nt" else "python")


def step(text: str) -> None:
    print(f"\n==> {text}", flush=True)


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, shell=(os.name == "nt" and cmd[0] == "npm"))


def write_env_files() -> None:
    backend_env, simulator_env = ROOT / "backend" / ".env", ROOT / "simulator" / ".env"
    if backend_env.exists() and simulator_env.exists():
        print("backend/.env and simulator/.env already exist - leaving them unchanged.")
        return
    api_key, webhook_secret = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
    replacements = {
        "change-me-to-a-long-random-string": secrets.token_urlsafe(40),
        "change-me": secrets.token_urlsafe(40),
        "local-dev-provider-key": api_key,
        "local-dev-webhook-secret": webhook_secret,
    }
    for example, target in [(backend_env.with_name(".env.example"), backend_env),
                            (simulator_env.with_name(".env.example"), simulator_env)]:
        text = example.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")
        print(f"Wrote {target.relative_to(ROOT)}")


def main() -> None:
    if sys.version_info < (3, 11):
        sys.exit("Python 3.11 or newer is required.")
    if not shutil.which("node") or not shutil.which("npm"):
        sys.exit("Node.js 18.18+ (with npm) is required: https://nodejs.org")

    step("Creating Python virtual environment (.venv)")
    if not PYTHON.exists():
        venv.create(VENV, with_pip=True)
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip", "-q"])

    step("Installing Python packages")
    run([str(PYTHON), "-m", "pip", "install", "-q", "-r", "requirements-dev.txt"])

    step("Writing local configuration (.env files)")
    write_env_files()

    step("Creating databases")
    run([str(PYTHON), "manage.py", "migrate", "--noinput"], cwd=ROOT / "backend")
    run([str(PYTHON), "manage.py", "migrate", "--noinput"], cwd=ROOT / "simulator")

    step("Loading demo data")
    seeded = run([str(PYTHON), "manage.py", "seed_demo"], cwd=ROOT / "backend", check=False)
    if seeded.returncode != 0:
        print("Demo data already present (use 'python manage.py seed_demo --reset' in backend/ to start over).")

    step("Installing frontend packages (this can take a few minutes)")
    run(["npm", "ci"], cwd=ROOT / "frontend")

    print("\nSetup complete. Start everything with:\n\n    python scripts/dev.py\n\nthen open http://localhost:3000")


if __name__ == "__main__":
    main()
