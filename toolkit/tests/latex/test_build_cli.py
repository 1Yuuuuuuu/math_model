import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.latex.build import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable

MINIMAL_DOC = r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{SimSun}
\begin{document}
\section{引言}\label{sec:intro}
内容。
\end{document}
"""


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.latex.build", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _write_doc(tmp_path: Path) -> Path:
    (tmp_path / "main.tex").write_text(MINIMAL_DOC, encoding="utf-8")
    return tmp_path


def test_cli_build_success_subprocess(tmp_path: Path) -> None:
    work = _write_doc(tmp_path)
    proc = _run_cli("--dir", str(work), "--passes", "1")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "ok"
    assert report["pages"] is not None and report["pages"] >= 1
    assert report["pdf_path"].endswith("main.pdf")
    assert report["log_path"].endswith("main.log")
    assert (work / "main.pdf").is_file()


def test_cli_missing_main_tex_fails_closed(tmp_path: Path) -> None:
    proc = _run_cli("--dir", str(tmp_path))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "main.tex" in payload["error"]


def test_cli_xelatex_missing_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    import cumcm_toolkit.latex.build as build_module

    monkeypatch.setattr(build_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.latex.build", "--dir", str(tmp_path)])
    code = cli_main()
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "xelatex" in payload["error"]


def test_cli_doc_with_error_reports_failed_build(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}\undefinedcmd{1}\end{document}", encoding="utf-8")
    proc = _run_cli("--dir", str(tmp_path), "--passes", "1")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "failed"
    assert report["errors"]
