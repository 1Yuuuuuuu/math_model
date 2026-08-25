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


def test_lint_detects_cref_unresolved(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "见~\\cref{sec:missing}~节。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "failed"
    assert any(i["kind"] == "unresolved_ref" and "sec:missing" in i["message"] for i in report["issues"])


def test_lint_star_ref_resolves(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\\label{sec:a}\n"
        "见~\\ref*{sec:a}。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"
    assert not any(i["kind"] == "unresolved_ref" for i in report["issues"])


def test_lint_todo_png_is_not_placeholder(tmp_path: Path) -> None:
    (tmp_path / "TODO.png").write_bytes(b"x")
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\includegraphics{TODO.png}\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"
    assert not any(i["kind"] == "placeholder" for i in report["issues"])


def test_lint_cite_without_bib_warns(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "见~\\cite{src_unknown}。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"  # warning severity: detailed checks live in citation_check
    assert any(i["kind"] == "cite_without_bib" for i in report["issues"])
    assert all(i["severity"] == "warning" for i in report["issues"] if i["kind"] == "cite_without_bib")


def test_lint_cite_with_bib_entry_does_not_warn(tmp_path: Path) -> None:
    (tmp_path / "bibliography.bib").write_text("@article{src_known,\n  title={示例},\n}\n", encoding="utf-8")
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "见~\\cite{src_known}。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert not any(i["kind"] == "cite_without_bib" for i in report["issues"])


def test_lint_unescaped_percent_warns(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "使用 50% 的样本。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert report["status"] == "ok"  # warning severity
    assert any(i["kind"] == "unescaped_percent" for i in report["issues"])


def test_lint_escaped_percent_does_not_warn(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "准确率 50\\% 达标。\n"
        "\\end{document}\n",
    )
    report = lint_paper(tmp_path)
    assert not any(i["kind"] == "unescaped_percent" for i in report["issues"])


def test_lint_missing_main_tex_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        lint_paper(tmp_path)
