import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.latex.citation_check import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.latex.citation_check", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _write_files(tmp_path: Path, tex: str, bib: str) -> tuple[Path, Path]:
    tex_path = tmp_path / "paper.tex"
    bib_path = tmp_path / "refs.bib"
    tex_path.write_text(tex, encoding="utf-8")
    bib_path.write_text(bib, encoding="utf-8")
    return tex_path, bib_path


def test_cli_success_subprocess(tmp_path: Path) -> None:
    tex, bib = _write_files(
        tmp_path,
        "\\documentclass{article}\n\\begin{document}\n见~\\cite{src_abcdef12}。\n\\end{document}\n",
        "@misc{src_abcdef12,\n  title = {T},\n}\n",
    )
    proc = _run_cli(
        "--tex", str(tex),
        "--bib", str(bib),
        "--citations", '[{"source_id": "src_abcdef12"}]',
        "--approved-source-ids", '["src_abcdef12"]',
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "ok"
    assert report["missing_bibtex"] == []
    assert report["unapproved_sources"] == []


def test_cli_reports_missing_bibtex_but_exits_zero(tmp_path: Path) -> None:
    tex, bib = _write_files(
        tmp_path,
        "\\documentclass{article}\n\\begin{document}\n见~\\cite{src_nope}。\n\\end{document}\n",
        "",
    )
    proc = _run_cli(
        "--tex", str(tex),
        "--bib", str(bib),
        "--citations", "[]",
        "--approved-source-ids", "[]",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "failed"
    assert "src_nope" in report["missing_bibtex"]


def test_cli_missing_tex_file_fails_closed(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text("", encoding="utf-8")
    proc = _run_cli(
        "--tex", str(tmp_path / "nope.tex"),
        "--bib", str(bib),
        "--citations", "[]",
        "--approved-source-ids", "[]",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_bad_citations_json_fails_closed(tmp_path: Path) -> None:
    tex, bib = _write_files(tmp_path, "x", "")
    proc = _run_cli(
        "--tex", str(tex),
        "--bib", str(bib),
        "--citations", "[{",
        "--approved-source-ids", "[]",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_citations_not_array_fails_closed(tmp_path: Path) -> None:
    tex, bib = _write_files(tmp_path, "x", "")
    proc = _run_cli(
        "--tex", str(tex),
        "--bib", str(bib),
        "--citations", '{"source_id": "src_x"}',
        "--approved-source-ids", "[]",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
