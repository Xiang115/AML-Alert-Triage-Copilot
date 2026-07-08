from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def backend_python() -> str:
    if os.name == "nt":
        candidate = BACKEND / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = BACKEND / ".venv" / "bin" / "python"
    return str(candidate if candidate.exists() else sys.executable)


def npm_cmd() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def run(label: str, cmd: list[str], cwd: Path) -> None:
    print(f"\n==> {label}")
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    py = backend_python()
    run_id = f"{os.getpid()}-{time.time_ns()}"
    pytest_run_dir = BACKEND / "work" / "pytest-runs" / run_id
    pytest_run_dir.mkdir(parents=True, exist_ok=True)
    pytest_temp = f"work/pytest-runs/{run_id}/tmp"
    pytest_cache = f"work/pytest-runs/{run_id}/cache"
    steps = [
        (
            "backend tests",
            [
                py,
                "-m",
                "pytest",
                "-q",
                "--basetemp",
                pytest_temp,
                "-o",
                f"cache_dir={pytest_cache}",
            ],
            BACKEND,
        ),
        ("backend readiness", [py, "-m", "readiness"], BACKEND),
        ("frontend verify", [npm_cmd(), "run", "verify"], FRONTEND),
    ]
    for label, cmd, cwd in steps:
        run(label, cmd, cwd)
    print("\nAll verification checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
