import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.evaluation.baselines import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.evaluation.baselines", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.evaluation.baselines", *argv])
    return cli_main()


def test_cli_mean_baseline_success_subprocess() -> None:
    proc = _run_cli("--strategy", "mean", "--y", "[1,2,3]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload == {"strategy": "mean", "value": 2.0}


def test_cli_median_baseline_success() -> None:
    proc = _run_cli("--strategy", "median", "--y", "[1,2,10]")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload == {"strategy": "median", "value": 2.0}


def test_cli_compare_success_subprocess() -> None:
    proc = _run_cli("--compare", "--y-true", "[1,2,3]", "--y-pred", "[1,2,4]", "--baseline-value", "2")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["metric"] == "rmse"
    assert payload["model_score"] == pytest.approx((1 / 3) ** 0.5)
    assert payload["baseline_score"] == pytest.approx((2 / 3) ** 0.5)
    assert payload["improvement"] == pytest.approx(0.292893, abs=1e-5)


def test_cli_unknown_strategy_fails_closed() -> None:
    proc = _run_cli("--strategy", "bogus", "--y", "[1,2,3]")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "bogus" in payload["error"]


def test_cli_no_mode_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--y", "[1,2,3]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_compare_missing_baseline_value_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--compare", "--y-true", "[1,2]", "--y-pred", "[1,2]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_bad_json_y_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--strategy", "mean", "--y", "[1,")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--strategy", "mean", "--y", "[NaN]")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_compare_nonfinite_baseline_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--compare", "--y-true", "[1,2]", "--y-pred", "[1,2]", "--baseline-value", "nan")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
