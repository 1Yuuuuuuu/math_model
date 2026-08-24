import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.environment import doctor as doctor_module
from cumcm_toolkit.environment.doctor import _uv_path, doctor


def fake_which(present: set[str]) -> object:
    def lookup(name: str) -> str | None:
        if name in present:
            return f"C:/tools/{name}.exe"
        return None

    return lookup


def test_doctor_reports_ok_when_all_toolchains_present() -> None:
    payload = doctor(fake_which({"uv", "xelatex", "latexmk"}), probe=lambda _: True)
    assert payload["status"] == "ok"
    assert payload["errors"] == []
    names = {check["name"]: check for check in payload["checks"]}
    assert set(names) == {"python", "uv", "xelatex", "latexmk"}
    assert names["uv"]["found"] == "C:/tools/uv.exe"
    assert names["uv"]["ok"] is True


def test_doctor_fails_closed_on_missing_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "_uv_path", lambda _which: None)
    payload = doctor(fake_which({"xelatex", "latexmk"}), probe=lambda _: True)
    assert payload["status"] == "failed"
    uv = next(check for check in payload["checks"] if check["name"] == "uv")
    assert uv["ok"] is False
    assert uv["found"] is None


def test_doctor_never_guesses_when_probe_errors() -> None:
    def broken_lookup(name: str) -> str | None:
        if name == "latexmk":
            raise OSError("probe exploded")
        return fake_which({"uv", "xelatex"})(name)

    payload = doctor(broken_lookup, probe=lambda _: True)
    assert payload["status"] == "failed"
    latexmk = next(check for check in payload["checks"] if check["name"] == "latexmk")
    assert latexmk["ok"] is False
    assert any("latexmk" in error for error in payload["errors"])


def test_doctor_flags_present_but_broken_tool() -> None:
    def probe(path: str) -> bool:
        return not path.endswith("latexmk.exe")

    payload = doctor(fake_which({"uv", "xelatex", "latexmk"}), probe=probe)
    assert payload["status"] == "failed"
    latexmk = next(check for check in payload["checks"] if check["name"] == "latexmk")
    assert latexmk["found"] == "C:/tools/latexmk.exe"
    assert latexmk["ok"] is False


def test_doctor_uv_fallback_finds_bootstrapped_uv(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "repo"
    uv_dir = bootstrap_root / ".superpowers" / "bootstrap-uv" / "Scripts"
    uv_dir.mkdir(parents=True)
    (uv_dir / "uv.exe").write_bytes(b"fake uv")

    def no_uv(name: str) -> str | None:
        return None

    assert _uv_path(no_uv, bootstrap_root=bootstrap_root) == str(uv_dir / "uv.exe")


def test_doctor_uv_fallback_absent_returns_none(tmp_path: Path) -> None:
    def no_uv(name: str) -> str | None:
        return None

    assert _uv_path(no_uv, bootstrap_root=tmp_path / "empty") is None


def test_doctor_cli_emits_stable_json(tmp_path: Path, project_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.environment.doctor"],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": str(project_root / "toolkit" / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    assert set(payload) == {"doctor_version", "status", "checks", "errors"}
    assert payload["doctor_version"] == "1.0"
