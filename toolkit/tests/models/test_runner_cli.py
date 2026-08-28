import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.models.runner import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.models.runner", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.models.runner", *argv])
    return cli_main()


def test_cli_linear_regression_success_subprocess() -> None:
    proc = _run_cli("--name", "linear-regression", "--X", "[[1,2],[3,4],[5,6]]", "--y", "[3,7,11]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload == {"status": "ok", "model": "linear-regression", "params": {}, "seed": None, "fitted": True}


def test_cli_decision_tree_with_params_and_seed_success_subprocess() -> None:
    proc = _run_cli(
        "--name", "decision-tree",
        "--X", "[[0,0],[1,1],[2,2],[3,3]]",
        "--y", "[0,1,0,1]",
        "--seed", "7",
        "--params", '{"max_depth": 1}',
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert payload["model"] == "decision-tree"
    assert payload["params"] == {"max_depth": 1}
    assert payload["seed"] == 7
    assert payload["fitted"] is True


def test_cli_unknown_model_fails_closed() -> None:
    proc = _run_cli("--name", "nope", "--X", "[[1]]", "--y", "[1]")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "unknown model" in payload["error"]


def test_cli_seed_random_state_conflict_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(
        monkeypatch, capsys,
        "--name", "decision-tree", "--X", "[[0],[1]]", "--y", "[0,1]",
        "--seed", "7", "--params", '{"random_state": 3}',
    )
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "conflict" in payload["error"]


def test_cli_fit_failure_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--name", "linear-regression", "--X", "[[1,2],[3,4]]", "--y", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "fit failed" in payload["error"]


def test_cli_bad_json_X_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--name", "linear-regression", "--X", "[[1,", "--y", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_params_not_object_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--name", "linear-regression", "--X", "[[1]]", "--y", "[1]", "--params", "[1,2]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "object" in payload["error"]


def test_cli_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--name", "linear-regression", "--X", "[[NaN]]", "--y", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
