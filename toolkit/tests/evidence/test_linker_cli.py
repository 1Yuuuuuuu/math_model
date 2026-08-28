import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.evidence.linker import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable

VALID_CLAIM = (
    '{"claim_id": "clm_method_choice", "claim_text": "采用熵权法确定权重", '
    '"artifact_id": "art_result_table", "experiment_id": "exp_model_run", '
    '"locator": {"kind": "table", "value": "表1"}, "boundary": "仅覆盖熵权法权重计算"}'
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.evidence.linker", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.evidence.linker", *argv])
    return cli_main()


def test_cli_success_subprocess() -> None:
    proc = _run_cli("--claim", VALID_CLAIM)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    record = json.loads(proc.stdout)
    assert record["schema_version"] == "1.0"
    assert record["claim_id"] == "clm_method_choice"
    assert record["artifact_id"] == "art_result_table"
    assert record["locator"] == {"kind": "table", "value": "表1"}


def test_cli_missing_field_fails_closed() -> None:
    proc = _run_cli("--claim", '{"claim_id": "clm_x", "claim_text": "t", "artifact_id": "art_x", "experiment_id": "exp_x", "locator": {"kind": "table", "value": "表1"}}')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "boundary" in payload["error"]


def test_cli_contract_violation_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    claim = json.loads(VALID_CLAIM)
    claim["claim_id"] = "not-a-claim-id"
    code = _call_main(monkeypatch, capsys, "--claim", json.dumps(claim))
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_bad_json_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--claim", '{"claim_id":')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_claim_not_object_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--claim", '["clm_x"]')
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    claim = '{"claim_id": "clm_x", "claim_text": "t", "artifact_id": "art_x", "experiment_id": "exp_x", "locator": {"kind": "table", "value": NaN}, "boundary": "b"}'
    code = _call_main(monkeypatch, capsys, "--claim", claim)
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
