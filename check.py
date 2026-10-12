#!/usr/bin/env python3
"""Run all quality checks matching `make check`."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# Detect python in venv if present
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

RUFF = VENV_PYTHON.parent / ("ruff.exe" if sys.platform == "win32" else "ruff")
MYPY = VENV_PYTHON.parent / ("mypy.exe" if sys.platform == "win32" else "mypy")
PYTEST = VENV_PYTHON.parent / ("pytest.exe" if sys.platform == "win32" else "pytest")


def run(cmd: list[str], cwd: Path, name: str) -> None:
    print(f"\n=== Running: {name} ({' '.join(cmd)}) ===")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"FAILED: {name} (exit code {res.returncode})", file=sys.stderr)
        sys.exit(res.returncode)
    print(f"PASSED: {name}")


def main() -> None:
    # Backend checks
    run([str(RUFF), "check", "."], BACKEND_DIR, "Backend ruff check")
    run([str(RUFF), "format", "--check", "."], BACKEND_DIR, "Backend ruff format")
    run(
        [str(MYPY), "trucksafe/domain", "trucksafe/services"],
        BACKEND_DIR,
        "Backend mypy",
    )
    run([str(PYTEST), "-q"], BACKEND_DIR, "Backend pytest")

    # Frontend checks
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm_cmd, "run", "lint"], FRONTEND_DIR, "Frontend eslint")
    run([npm_cmd, "run", "typecheck"], FRONTEND_DIR, "Frontend typecheck")
    run([npm_cmd, "test", "--", "--run"], FRONTEND_DIR, "Frontend vitest")
    run([npm_cmd, "run", "build"], FRONTEND_DIR, "Frontend build")

    print("\n==============================================")
    print("ALL CHECKS PASSED SUCCESSFULLY! (GATE GREEN)")
    print("==============================================")


if __name__ == "__main__":
    main()
