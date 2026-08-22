from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from typing import Callable


REQUIRED_PYTHON = (3, 11)


@dataclass
class Check:
    name: str
    required: bool
    found: object
    ok: bool
    details: str = ""


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
) -> Check:
    path = None
    error = ""
    try:
        path = which(name)
    except Exception as exc:  # noqa: BLE001 - fail-closed on any probe error
        error = str(exc)
    return Check(name=name, required=required, found=path, ok=path is not None and not error, details=error)


def doctor(which: Callable[[str], str | None] = shutil.which) -> dict[str, object]:
    checks = [
        _check_python(),
        _check_executable("uv", True, which),
        _check_executable("xelatex", True, which),
        _check_executable("latexmk", True, which),
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
