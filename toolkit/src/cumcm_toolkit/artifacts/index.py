from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from scripts.contract_formats import is_cumcm_workspace_path
from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "artifact.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)

IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".superpowers", ".venv", ".worktrees"}

KIND_BY_SUFFIX = {
    ".csv": "data", ".xlsx": "data", ".xls": "data",
    ".py": "code", ".ipynb": "code", ".r": "code", ".jl": "code",
    ".png": "figure", ".jpg": "figure", ".jpeg": "figure", ".svg": "figure",
    ".pdf": "pdf", ".tex": "latex",
    ".md": "report", ".json": "config", ".yml": "config", ".yaml": "config",
}


def classify_kind(path: Path) -> str:
    return KIND_BY_SUFFIX.get(path.suffix.lower(), "other")


def derive_artifact_id(relative: str, sha256: str) -> str:
    digest = hashlib.sha256(f"{relative}\n{sha256}".encode("utf-8")).hexdigest()
    return f"art_{digest[:24]}"


def make_artifact_record(
    root: Path,
    relative: str,
    sha256: str,
    created_at: str,
    classify: Callable[[Path], str],
) -> dict[str, object]:
    if not is_cumcm_workspace_path(relative):
        raise ValueError(f"non-portable path in workspace: {relative}")
    record: dict[str, object] = {
        "schema_version": "1.0",
        "artifact_id": derive_artifact_id(relative, sha256),
        "kind": classify(root / relative),
        "path": relative,
        "sha256": sha256,
        "created_at": created_at,
        "source_artifact_ids": [],
    }
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"artifact record invalid: {errors[0].message}")
    return record


def index_artifacts(
    workspace_root: Path,
    *,
    classify: Callable[[Path], str] = classify_kind,
    now: Callable[[], datetime] | None = None,
) -> list[dict[str, object]]:
    root = workspace_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"workspace root not found: {root}")
    records = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        relative_posix = relative.as_posix()
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        created = (now() if now else datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
        records.append(
            make_artifact_record(
                root, relative_posix, sha256, created.isoformat(timespec="seconds"), classify
            )
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Index workspace artifacts")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        records = index_artifacts(args.root)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(records, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
