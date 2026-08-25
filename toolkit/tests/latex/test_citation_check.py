import pytest

from cumcm_toolkit.latex.citation_check import citation_check


def _citation(source_id: str = "src_synthetic_method") -> dict:
    return {
        "schema_version": "1.0",
        "citation_id": "cite_synthetic_method",
        "claim_id": "clm_method_choice",
        "source_id": source_id,
        "usage": "method",
        "locator": {"kind": "paragraph", "value": "第 2 段"},
        "support_boundary": "仅支持方法性主张",
        "verified_at": "2026-08-22T00:00:00+00:00",
    }


def _bib(source_id: str = "src_synthetic_method") -> str:
    return f"@article{{{source_id},\n  title={{示例}},\n}}\n"


def test_citation_check_ok() -> None:
    tex = "\\documentclass{article}\n\\begin{document}\n见~\\cite{src_synthetic_method}。\n\\end{document}\n"
    report = citation_check(tex, _bib(), [_citation()], approved_source_ids={"src_synthetic_method"})
    assert report["status"] == "ok"
    assert report["errors"] == []
    assert report["orphaned_citations"] == []


def test_citation_check_requires_approved_source_ids() -> None:
    tex = "\\begin{document}\\cite{src_synthetic_method}\\end{document}"
    with pytest.raises(TypeError):
        citation_check(tex, _bib(), [_citation()])  # type: ignore[call-arg]


def test_citation_check_missing_bibtex_entry() -> None:
    tex = "\\begin{document}\\cite{src_unknown}\\end{document}"
    report = citation_check(tex, _bib(), [_citation()], approved_source_ids={"src_synthetic_method"})
    assert report["status"] == "failed"
    assert "src_unknown" in report["missing_bibtex"]


def test_citation_check_uncited_entry() -> None:
    tex = "\\begin{document}no citations\\end{document}"
    report = citation_check(tex, _bib(), [_citation()], approved_source_ids={"src_synthetic_method"})
    assert report["status"] == "failed"
    assert "src_synthetic_method" in report["uncited_entries"]


def test_citation_check_unmatched_citation() -> None:
    tex = "\\begin{document}\\cite{src_synthetic_method}\\end{document}"
    report = citation_check(tex, _bib(), [], approved_source_ids=set())
    assert report["status"] == "failed"
    assert "src_synthetic_method" in report["unmatched_citations"]


def test_citation_check_unapproved_source() -> None:
    tex = "\\begin{document}\\cite{src_synthetic_method}\\end{document}"
    citations = [_citation()]
    report = citation_check(tex, _bib(), citations, approved_source_ids=set())
    assert report["status"] == "failed"
    assert "src_synthetic_method" in report["unapproved_sources"]


def test_citation_check_unapproved_with_explicit_set() -> None:
    # The approved set is explicit and authoritative: an empty set approves nothing.
    tex = "\\begin{document}\\cite{src_synthetic_method}\\end{document}"
    report = citation_check(
        tex, _bib(), [_citation()], approved_source_ids=set()
    )
    assert report["status"] == "failed"
    assert "src_synthetic_method" in report["unapproved_sources"]


def test_citation_check_orphaned_citation_link() -> None:
    # The citation chain knows src_x (and its derived bib key) but the bib has
    # no entry for it: orphaned citation link, must fail.
    tex = "\\begin{document}no citations\\end{document}"
    report = citation_check(tex, "", [_citation(source_id="src_x")], approved_source_ids={"src_x"})
    assert report["status"] == "failed"
    assert "src_x" in report["orphaned_citations"]
    assert any("citation link without bib entry" in error for error in report["errors"])
