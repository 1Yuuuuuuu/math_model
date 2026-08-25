import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.evaluation.sensitivity import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.evaluation.sensitivity", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.evaluation.sensitivity", *argv])
    return cli_main()


def test_cli_validate_success_subprocess() -> None:
    payload = '{"base_params": {"a": 1.0, "b": 2.0}, "perturb": {"a": [0.9, 1.0, 1.1], "b": [1.5, 2.0]}}'
    proc = _run_cli("--validate", payload)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result == {"status": "ok", "valid": True}


def test_cli_validate_not_an_object_fails_closed() -> None:
    proc = _run_cli("--validate", "[1, 2, 3]")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_validate_missing_base_params_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"perturb": {"a": [1.0]}}')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "base_params" in payload["error"]


def test_cli_validate_missing_perturb_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"base_params": {"a": 1.0}}')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "perturb" in payload["error"]


def test_cli_validate_perturb_not_list_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"base_params": {"a": 1.0}, "perturb": {"a": 1.0}}')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "perturb.a" in payload["error"]


def test_cli_validate_base_param_not_number_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"base_params": {"a": "x"}, "perturb": {"a": [1.0]}}')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "base_params.a" in payload["error"]


def test_cli_validate_bad_json_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"base_params":')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_validate_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--validate", '{"base_params": {"a": NaN}, "perturb": {"a": [1.0]}}')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
