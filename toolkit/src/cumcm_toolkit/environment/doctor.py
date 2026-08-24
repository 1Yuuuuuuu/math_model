from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REQUIRED_PYTHON = (3, 11)


@dataclass
class Check:
    name: str
    required: bool
    found: object
    ok: bool
    details: str = ""


def _probe_runs(path: str, timeout: float = 10.0) -> bool:
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _uv_path(
    which: Callable[[str], str | None],
    bootstrap_root: Path | None = None,
) -> str | None:
    found = which("uv")
    if found is not None:
        return found
    root = bootstrap_root if bootstrap_root is not None else Path(__file__).resolve().parents[4]
    bootstrap = root / ".superpowers" / "bootstrap-uv" / "Scripts" / "uv.exe"
    return str(bootstrap) if bootstrap.is_file() else None


def _check_python() -> Check:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = (sys.version_info.major, sys.version_info.minor) == REQUIRED_PYTHON
    return Check(
        name="python",
        required=True,
        found=version,
        ok=ok,
        details=("" if ok else f"need {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}.x"),
    )


def _check_executable(
    name: str,
    required: bool,
    which: Callable[[str], str | None],
    probe: Callable[[str], bool],
    resolve: Callable[[str], str | None] | None = None,
) -> Check:
    path = None
    error = ""
    try:
        path = which(name) if resolve is None else resolve(name)
    except Exception as exc:  # noqa: BLE001 - fail-closed on any probe error
        error = str(exc)
    ok = path is not None and not error and probe(path)
    return Check(name=name, required=required, found=path, ok=ok, details=error)


def doctor(
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[str], bool] = _probe_runs,
) -> dict[str, object]:
    checks = [
        _check_python(),
        _check_executable("uv", True, which, probe, resolve=lambda _name: _uv_path(which)),
        _check_executable("xelatex", True, which, probe),
        _check_executable("latexmk", True, which, probe),
    ]
    errors = sorted(f"{c.name}: {c.details}" for c in checks if c.details)
    failed = [c.name for c in checks if c.required and not c.ok]
    return {
        "doctor_version": "1.0",
        "status": "ok" if not failed else "failed",
        "checks": [
            {"name": c.name, "required": c.required, "found": c.found, "ok": c.ok}
            for c in checks
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CUMCM workbench environment doctor")
    parser.parse_args()
    payload = doctor()
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
