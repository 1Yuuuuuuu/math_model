import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cumcm_toolkit.artifacts.index import (
    classify_kind,
    derive_artifact_id,
    index_artifacts,
    make_artifact_record,
)
from scripts.validate_contracts import load_json, make_validator

FIXED = datetime(2026, 8, 22, 1, 0, 0, tzinfo=timezone.utc)


def write_workspace(root: Path) -> None:
    (root / "data").mkdir()
    (root / "code").mkdir()
    (root / "data" / "input.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "code" / "solve.py").write_text("print(1)\n", encoding="utf-8")
    (root / "README.md").write_text("# ws\n", encoding="utf-8")


def test_index_artifacts_produces_valid_phase0_records(project_root: Path, tmp_path: Path) -> None:
    write_workspace(tmp_path)
    records = index_artifacts(tmp_path, now=lambda: FIXED)
    schema = load_json(project_root / "shared/contracts/artifact.schema.json")
    validator = make_validator(schema)
    for record in records:
        assert list(validator.iter_errors(record)) == []
    paths = {record["path"] for record in records}
    assert paths == {"data/input.csv", "code/solve.py", "README.md"}
    kinds = {record["path"]: record["kind"] for record in records}
    assert kinds["data/input.csv"] == "data"
    assert kinds["code/solve.py"] == "code"


def test_index_artifacts_is_deterministic(tmp_path: Path) -> None:
    write_workspace(tmp_path)
    first = index_artifacts(tmp_path, now=lambda: FIXED)
    second = index_artifacts(tmp_path, now=lambda: FIXED)
    assert first == second


def test_index_skips_gitkeep_and_caches(tmp_path: Path) -> None:
    write_workspace(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    records = index_artifacts(tmp_path, now=lambda: FIXED)
    paths = {record["path"] for record in records}
    assert "artifacts/.gitkeep" not in paths
    assert all("__pycache__" not in path for path in paths)


def test_make_artifact_record_rejects_non_portable_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_artifact_record(
            tmp_path,
            "data/NUL.txt",
            "a" * 64,
            FIXED.isoformat(timespec="seconds"),
            classify_kind,
        )


def test_derive_artifact_id_is_stable_and_prefixed() -> None:
    first = derive_artifact_id("data/input.csv", "a" * 64)
    second = derive_artifact_id("data/input.csv", "a" * 64)
    assert first == second
    assert first.startswith("art_")
    assert len(first) == 4 + 24


def test_index_cli_emits_json(tmp_path: Path, project_root: Path) -> None:
    write_workspace(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.artifacts.index", "--root", str(tmp_path)],
        cwd=project_root, capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(project_root / "toolkit" / "src") + os.pathsep + str(project_root)},
    )
    assert result.returncode == 0
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    assert {record["path"] for record in records} == {"data/input.csv", "code/solve.py", "README.md"}
