import shutil
import subprocess
from pathlib import Path

import pytest

from cumcm_toolkit.latex.bibliography import bib_key_for_source_id, generate_bibliography
from cumcm_toolkit.latex.build import build_paper

XELATEX = shutil.which("xelatex")

pytestmark = pytest.mark.skipif(not XELATEX, reason="xelatex not available")


def _write_doc(dir_path: Path, tex: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    main = dir_path / "main.tex"
    main.write_text(tex, encoding="utf-8")
    return main


GOOD_DOC = r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{SimSun}
\begin{document}
\section{引言}\label{sec:intro}
第~\ref{sec:conclusion}~节总结全文。
\section{结论}\label{sec:conclusion}
结论。
\end{document}
"""


def test_build_ok_reports_pages_and_no_undefined(tmp_path: Path) -> None:
    _write_doc(tmp_path, GOOD_DOC)
    report = build_paper(tmp_path)
    assert report["status"] == "ok"
    assert report["pages"] is not None and report["pages"] >= 1
    assert report["undefined_references"] == []
    assert report["pdf_path"].is_file()


def test_build_detects_undefined_reference(tmp_path: Path) -> None:
    _write_doc(
        tmp_path,
        r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{SimSun}
\begin{document}
\section{引言}
见第~\ref{sec:missing}~节。
\end{document}
""",
    )
    report = build_paper(tmp_path, passes=1)
    assert report["undefined_references"], "expected undefined reference with single pass"
    assert report["status"] == "failed", "undefined reference must fail the build (C1 fail-closed)"


def test_build_fails_on_undefined_reference_after_two_passes(tmp_path: Path) -> None:
    _write_doc(
        tmp_path,
        r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\setmainfont{SimSun}
\begin{document}
\section{引言}
见第~\ref{sec:missing}~节。
\end{document}
""",
    )
    report = build_paper(tmp_path, passes=2)
    assert report["status"] == "failed"
    assert report["undefined_references"], "undefined reference must fail the build even after two passes"
    assert report["failed_pass"] is None, "no individual pass failed; the fail-closed gate is the failure"


def test_build_fails_on_tex_error(tmp_path: Path) -> None:
    _write_doc(tmp_path, r"\documentclass{article}\begin{document}\undefinedcmd{1}\end{document}")
    report = build_paper(tmp_path)
    assert report["status"] == "failed"
    assert report["errors"], "expected error lines in log"
    assert report["log_path"].is_file()  # replaces the former tautological pdf assertion
    assert report["failed_pass"] == 1, "build must stop at the first failing pass"


def test_build_stops_after_first_failed_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_doc(tmp_path, GOOD_DOC)
    calls = {"n": 0}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["n"] += 1
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="")

    monkeypatch.setattr("cumcm_toolkit.latex.build.subprocess.run", fake_run)
    report = build_paper(tmp_path, passes=3)
    assert report["status"] == "failed"
    assert report["failed_pass"] == 1
    assert calls["n"] == 1, "build must early-stop after the first failed pass"


def test_build_timeout_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_doc(tmp_path, GOOD_DOC)

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr("cumcm_toolkit.latex.build.subprocess.run", fake_run)
    report = build_paper(tmp_path, timeout=0.001)
    assert report["status"] == "failed"
    assert any("timeout after" in error for error in report["errors"]), report["errors"]
    assert report["failed_pass"] == 1


def test_build_with_bibtex_resolves_citation(tmp_path: Path) -> None:
    source = {
        "source_id": "src_synthetic_method",
        "title": "示例性方法说明",
        "authors": ["甲", "乙"],
        "year": 2024,
    }
    key = bib_key_for_source_id(source["source_id"])
    (tmp_path / "bibliography.bib").write_text(generate_bibliography([source]), encoding="utf-8")
    _write_doc(
        tmp_path,
        "\\documentclass[11pt]{article}\n"
        "\\usepackage{fontspec}\n"
        "\\setmainfont{SimSun}\n"
        "\\begin{document}\n"
        f"见~\\cite{{{key}}}。\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{bibliography}\n"
        "\\end{document}\n",
    )
    report = build_paper(tmp_path)
    assert report["status"] == "ok", report["errors"]
    assert report["undefined_references"] == [], "the bibtex pass must resolve the citation"


def test_build_missing_bibtex_skips_pass_and_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = {
        "source_id": "src_synthetic_method",
        "title": "示例性方法说明",
    }
    key = bib_key_for_source_id(source["source_id"])
    (tmp_path / "bibliography.bib").write_text(generate_bibliography([source]), encoding="utf-8")
    _write_doc(
        tmp_path,
        "\\documentclass[11pt]{article}\n"
        "\\usepackage{fontspec}\n"
        "\\setmainfont{SimSun}\n"
        "\\begin{document}\n"
        f"见~\\cite{{{key}}}。\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{bibliography}\n"
        "\\end{document}\n",
    )
    real_which = shutil.which

    def _without_bibtex(name: str) -> str | None:
        return None if name == "bibtex" else real_which(name)

    monkeypatch.setattr("cumcm_toolkit.latex.build.shutil.which", _without_bibtex)
    report = build_paper(tmp_path)
    assert any("bibtex not found" in warning for warning in report["warnings"]), report["warnings"]
    # xelatex-only fallback runs; the unresolved citation then fails the build closed
    assert report["status"] == "failed"
    assert report["undefined_references"], "citation stays unresolved without the bibtex pass"


def test_build_missing_xelatex_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_xelatex() -> str | None:
        return None

    monkeypatch.setattr("cumcm_toolkit.latex.build.shutil.which", _no_xelatex)
    with pytest.raises(ValueError):
        build_paper(tmp_path)
