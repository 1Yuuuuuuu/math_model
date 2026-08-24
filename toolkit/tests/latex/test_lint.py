from pathlib import Path

import pytest

from cumcm_toolkit.latex.lint import lint_paper


def _write(d: Path, tex: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.tex").write_text(tex, encoding="utf-8")


def test_lint_clean_document(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Intro}\\label{sec:intro}\n"
        "见第~\\ref{sec:intro}~节。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"
    assert report["issues"] == []


def test_lint_detects_duplicate_label_and_unresolved_ref(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\\label{sec:x}\n"
        "\\section{B}\\label{sec:x}\n"
        "见~\\ref{sec:missing}~节。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "failed"
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "duplicate_label" in kinds
    assert "unresolved_ref" in kinds
    for issue in report["issues"]:
        if issue["severity"] == "error":
            assert issue["line"] >= 1


def test_lint_detects_placeholder_marker_and_missing_image(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "TODO: 补数据\n"
        "\\includegraphics{nope.png}\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "placeholder" in kinds
    assert "missing_image" in kinds


def test_lint_ok_with_unreferenced_label_as_info(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Only}\\label{sec:only}\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"
    assert any(issue["kind"] == "unreferenced_label" for issue in report["issues"])


def test_lint_missing_main_tex_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        lint_paper(tmp_path)
