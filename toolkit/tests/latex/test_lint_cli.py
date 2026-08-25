import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.latex.lint import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.latex.lint", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def test_cli_lint_clean_success_subprocess(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\section{引言}\\label{sec:intro}\n见第~\\ref{sec:intro}~节。\n\\end{document}\n",
        encoding="utf-8",
    )
    proc = _run_cli("--dir", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "ok"
    assert report["issues"] == []


def test_cli_lint_reports_issues_but_exits_zero(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nTODO 待补充\n\\end{document}\n",
        encoding="utf-8",
    )
    proc = _run_cli("--dir", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "failed"
    kinds = [issue["kind"] for issue in report["issues"]]
    assert "placeholder" in kinds


def test_cli_lint_missing_main_tex_fails_closed(tmp_path: Path) -> None:
    proc = _run_cli("--dir", str(tmp_path))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "main.tex" in payload["error"]


def test_cli_lint_resolves_bibliography(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n见~\\cite{src_abcdef12}。\n\\end{document}\n",
        encoding="utf-8",
    )
    (tmp_path / "bibliography.bib").write_text(
        "@misc{src_abcdef12,\n  title = {T},\n}\n",
        encoding="utf-8",
    )
    proc = _run_cli("--dir", str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "ok", report["issues"]
