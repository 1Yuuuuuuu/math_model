import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.latex.bibliography import bib_key_for_source_id
from cumcm_toolkit.latex.bibliography import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable

SOURCE = (
    '{"source_id": "src_synthetic_method", "title": "示例性方法说明", '
    '"authors": ["甲", "乙"], "year": 2024, "venue_or_repository": "合成仓库"}'
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.latex.bibliography", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def test_cli_success_subprocess() -> None:
    proc = _run_cli("--sources", f"[{SOURCE}]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    bibtex = payload["bibtex"]
    key = bib_key_for_source_id("src_synthetic_method")
    assert f"@article{{{key}," in bibtex
    assert "示例性方法说明" in bibtex
    assert "author" in bibtex
    # bibtex text must contain the original keys escaped, not literal newlines in the JSON line
    assert "\n" not in proc.stdout.strip()


def test_cli_sources_not_array_fails_closed() -> None:
    proc = _run_cli("--sources", SOURCE)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "array" in payload["error"]


def test_cli_missing_source_id_fails_closed() -> None:
    bad = '{"title": "no id"}'
    proc = _run_cli("--sources", f"[{bad}]")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_bad_json_fails_closed() -> None:
    proc = _run_cli("--sources", "[{")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_rejects_nonstandard_json_constant() -> None:
    proc = _run_cli("--sources", '[{"source_id": "src_x", "year": NaN}]')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
