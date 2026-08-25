import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cumcm_toolkit.data.transform import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.data.transform", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _write_input(tmp_path: Path) -> Path:
    path = tmp_path / "input.csv"
    pd.DataFrame({"a": [1.0, None, 3.0], "b": [1, 2, 3]}).to_csv(path, index=False)
    return path


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.data.transform", *argv])
    code = cli_main()
    return code


def test_cli_success_subprocess_applies_steps_and_round_trip(tmp_path: Path) -> None:
    src = _write_input(tmp_path)
    out = tmp_path / "out.csv"
    steps = '[{"op": "fill_missing", "columns": ["a"], "value": 0.0}, {"op": "drop_columns", "columns": ["b"]}]'
    proc = _run_cli("--input", str(src), "--steps", steps, "--output", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["steps_applied"] == 2
    assert result["warnings"] == []
    # round-trip: output file readable and reflects the steps
    reread = pd.read_csv(out)
    assert list(reread.columns) == ["a"]
    assert reread["a"].isna().sum() == 0
    assert reread["a"].tolist() == [1.0, 0.0, 3.0]


def test_cli_failed_missing_input_file_subprocess(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    proc = _run_cli("--input", str(tmp_path / "nope.csv"), "--steps", "[]", "--output", str(out))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "nope.csv" in payload["error"]
    assert not out.exists(), "no output file may be written on failure"


def test_cli_failed_bad_json_steps(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    src = _write_input(tmp_path)
    out = tmp_path / "out.csv"
    code = _call_main(monkeypatch, capsys, "--input", str(src), "--steps", '{"op":', "--output", str(out))
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert not out.exists()


def test_cli_failed_unknown_op(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    src = _write_input(tmp_path)
    out = tmp_path / "out.csv"
    code = _call_main(monkeypatch, capsys, "--input", str(src), "--steps", '[{"op": "teleport", "columns": ["a"]}]', "--output", str(out))
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "teleport" in payload["error"]


def test_cli_rejects_nonstandard_json_constant_in_steps(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    src = _write_input(tmp_path)
    out = tmp_path / "out.csv"
    code = _call_main(monkeypatch, capsys, "--input", str(src), "--steps", '[{"op": "fill_missing", "columns": ["a"], "value": NaN}]', "--output", str(out))
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert not out.exists()
