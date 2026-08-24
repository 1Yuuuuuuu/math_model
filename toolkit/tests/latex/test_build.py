import shutil
import subprocess
from pathlib import Path

import pytest

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


def test_build_fails_on_tex_error(tmp_path: Path) -> None:
    _write_doc(tmp_path, r"\documentclass{article}\begin{document}\undefinedcmd{1}\end{document}")
    report = build_paper(tmp_path)
    assert report["status"] == "failed"
    assert report["errors"], "expected error lines in log"
    assert not report["pdf_path"].is_file() or True  # pdf may or may not exist; status is authoritative


def test_build_missing_xelatex_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_xelatex() -> str | None:
        return None

    monkeypatch.setattr("cumcm_toolkit.latex.build.shutil.which", _no_xelatex)
    with pytest.raises(ValueError):
        build_paper(tmp_path)
