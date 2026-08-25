import re
from pathlib import Path

REQUIRED = ["## 是什么", "## 为什么重要", "## 常见误区", "## 在本工作台中的用法", "## 一句话总结"]

WRITING_DOCS = [
    "structure.md", "abstract.md", "figures-tables.md",
    "formulas-symbols.md", "citation-originality.md", "latex-debug.md",
]


def test_writing_docs_have_required_sections_and_no_markers(project_root: Path) -> None:
    markers = re.compile(r"TODO|TBD|FIXME|待定")
    for name in WRITING_DOCS:
        path = project_root / "shared" / "knowledge" / "writing" / name
        assert path.is_file(), f"missing writing doc: {name}"
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{name} missing {heading}"
        assert len(text.strip()) > 200, f"{name} too short"
        assert not markers.search(text), f"{name} contains unfinished marker"


def test_cumcm_template_present_with_evidence_contract(project_root: Path) -> None:
    template_dir = project_root / "shared" / "templates" / "latex" / "cumcm"
    main_tex = template_dir / "main.tex"
    assert main_tex.is_file(), "cumcm main.tex missing"
    text = main_tex.read_text(encoding="utf-8")
    assert "ctexart" in text
    assert "\\cite" in text
    assert "证据" in text or "证据链" in text
    assert (template_dir / "cumcm.sty").is_file()
    assert (template_dir / "bibliography.bib").is_file()


def test_citation_originality_doc_mandates_approval(project_root: Path) -> None:
    text = (project_root / "shared/knowledge/writing/citation-originality.md").read_text(encoding="utf-8")
    assert "候选" in text and "引用" in text
    assert "批准" in text or "人工确认" in text
    assert "引用量" in text or "期刊等级" in text
