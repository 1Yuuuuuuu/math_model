import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.evaluation.metrics import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.evaluation.metrics", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.evaluation.metrics", *argv])
    return cli_main()


def test_cli_regression_success_subprocess() -> None:
    proc = _run_cli("--kind", "regression", "--y-true", "[1,2,3]", "--y-pred", "[1,2,4]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == {"metrics"}
    metrics = payload["metrics"]
    assert set(metrics) == {"mse", "rmse", "mae", "r2"}
    assert metrics["mse"] == pytest.approx(1 / 3)
    assert metrics["rmse"] == pytest.approx((1 / 3) ** 0.5)


def test_cli_classification_success_with_positive_label() -> None:
    proc = _run_cli(
        "--kind", "classification",
        "--y-true", "[0,1,1,0]",
        "--y-pred", "[0,1,0,0]",
        "--positive-label", "1",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload["metrics"]) == {"accuracy", "precision", "recall", "f1"}
    assert payload["metrics"]["accuracy"] == pytest.approx(0.75)


def test_cli_classification_infers_positive_label() -> None:
    proc = _run_cli("--kind", "classification", "--y-true", "[0,1,1]", "--y-pred", "[0,1,0]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    metrics = json.loads(proc.stdout)["metrics"]
    assert metrics["recall"] == pytest.approx(0.5)


def test_cli_unknown_kind_fails_closed() -> None:
    proc = _run_cli("--kind", "bogus", "--y-true", "[1]", "--y-pred", "[1]")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "bogus" in payload["error"]


def test_cli_bad_json_y_true_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--kind", "regression", "--y-true", "[1,", "--y-pred", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_length_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--kind", "regression", "--y-true", "[1,2]", "--y-pred", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "length mismatch" in payload["error"]


def test_cli_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--kind", "regression", "--y-true", "[NaN]", "--y-pred", "[1]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
