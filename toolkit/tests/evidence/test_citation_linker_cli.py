import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.evidence.citation_linker import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable

APPROVED_SOURCE = (
    '{"schema_version": "1.0", "source_id": "src_synthetic_method", "title": "示例方法", '
    '"authors": ["甲", "乙"], "year": 2024, "venue_or_repository": "合成仓库", '
    '"identifiers": {}, "canonical_url": "https://example.invalid/method", '
    '"retrieved_at": "2026-08-22T00:00:00+00:00", "retrieval_backend": "user-provided", '
    '"verification_status": "approved", "artifact_ids": ["art_method_note"], '
    '"content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", '
    '"decision_id": "dec_outline_sources"}'
)

LOCATOR = '{"kind": "paragraph", "value": "第 2 段"}'


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.evidence.citation_linker", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.evidence.citation_linker", *argv])
    return cli_main()


def _base_args() -> tuple[str, ...]:
    return ("--source", APPROVED_SOURCE, "--claim-id", "clm_method_choice", "--usage", "method",
            "--locator", LOCATOR, "--support-boundary", "仅支持方法性主张")


def test_cli_success_subprocess() -> None:
    proc = _run_cli(*_base_args())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    record = json.loads(proc.stdout)
    assert record["schema_version"] == "1.0"
    assert record["source_id"] == "src_synthetic_method"
    assert record["claim_id"] == "clm_method_choice"
    assert record["citation_id"].startswith("cite_")
    assert "verified_at" in record


def test_cli_unapproved_source_fails_closed() -> None:
    source = json.loads(APPROVED_SOURCE)
    source["verification_status"] = "candidate"
    proc = _run_cli("--source", json.dumps(source), "--claim-id", "clm_x", "--usage", "method",
                    "--locator", LOCATOR, "--support-boundary", "b")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "approved" in payload["error"]


def test_cli_missing_decision_id_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source = json.loads(APPROVED_SOURCE)
    del source["decision_id"]
    code = _call_main(monkeypatch, capsys, "--source", json.dumps(source), "--claim-id", "clm_x",
                      "--usage", "method", "--locator", LOCATOR, "--support-boundary", "b")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "decision_id" in payload["error"]


def test_cli_bad_usage_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--source", APPROVED_SOURCE, "--claim-id", "clm_x",
                      "--usage", "bogus", "--locator", LOCATOR, "--support-boundary", "b")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_bad_locator_json_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--source", APPROVED_SOURCE, "--claim-id", "clm_x",
                      "--usage", "method", "--locator", "{bad", "--support-boundary", "b")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_bad_source_json_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--source", '{"source_id":', "--claim-id", "clm_x",
                      "--usage", "method", "--locator", LOCATOR, "--support-boundary", "b")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_source_not_object_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--source", "[1,2]", "--claim-id", "clm_x",
                      "--usage", "method", "--locator", LOCATOR, "--support-boundary", "b")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
