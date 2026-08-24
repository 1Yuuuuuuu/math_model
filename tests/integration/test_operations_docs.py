from pathlib import Path


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def template_files(root: Path) -> set[str]:
    template = root / "shared" / "templates" / "project"
    return {
        path.relative_to(template).as_posix()
        for path in template.rglob("*")
        if path.is_file()
    }


def test_environment_doc_covers_every_doctor_check(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/environment.md")
    for name in ("python", "uv", "xelatex", "latexmk"):
        assert f"`{name}`" in doc
    assert "bootstrap.ps1" in doc
    assert "check_environment.ps1" in doc


def test_workspace_layout_doc_matches_template_tree(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/workspace-layout.md")
    for relative in template_files(project_root):
        assert relative in doc, f"template file missing from layout doc: {relative}"
    assert "默认不覆盖" in doc
    assert "artifacts/index.json" in doc
    assert "experiments/<experiment_id>.json" in doc


def test_template_tree_matches_layout_doc_rows(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/workspace-layout.md")
    rows = []
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "`" in stripped:
            first = stripped.strip("|").split("|")[0].strip().strip("`")
            if first.endswith("/") or first.endswith(".md"):
                rows.append(first)
    for row in rows:
        assert (project_root / "shared" / "templates" / "project" / row).exists(), (
            f"layout doc row not in template: {row}"
        )
