import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.results.export import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.results.export", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def test_cli_json_success_subprocess_and_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    proc = _run_cli("--json", '{"a": 1, "b": [2, 3]}', "--out", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload == {"status": "ok", "path": str(out.resolve()), "format": "json"}
    assert json.loads(out.read_text(encoding="utf-8")) == {"a": 1, "b": [2, 3]}


def test_cli_csv_success_subprocess_and_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    proc = _run_cli("--csv", '[{"a": 1, "b": 2}, {"a": 3, "b": 4}]', "--out", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert payload["format"] == "csv"
    assert payload["path"] == str(out.resolve())
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_cli_latex_success_subprocess(tmp_path: Path) -> None:
    out = tmp_path / "table.tex"
    proc = _run_cli("--latex", "--rows", '[{"a": 1, "b": 2}]', "--out", str(out), "--caption", "结果表")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "ok"
    assert payload["format"] == "latex"
    text = out.read_text(encoding="utf-8")
    assert "\\begin{table}" in text
    assert "\\caption{结果表}" in text
    assert "\\toprule" in text


def test_cli_no_mode_fails_closed(tmp_path: Path) -> None:
    proc = _run_cli("--out", str(tmp_path / "x.json"))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_multiple_modes_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--json", "1", "--csv", "[1]", "--out", str(tmp_path / "x")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_bad_json_data_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--json", "{bad", "--out", str(tmp_path / "x.json")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert not (tmp_path / "x.json").exists()


def test_cli_csv_empty_rows_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--csv", "[]", "--out", str(tmp_path / "x.csv")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_csv_not_array_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--csv", '{"a": 1}', "--out", str(tmp_path / "x.csv")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_csv_non_dict_rows_fail_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--csv", "[1, 2]", "--out", str(tmp_path / "x.csv")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_latex_non_dict_rows_fail_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--latex", "--rows", '["x"]', "--out", str(tmp_path / "x.tex")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"


def test_cli_rejects_nonstandard_json_constant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.results.export", "--json", '{"a": NaN}', "--out", str(tmp_path / "x.json")])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
