from pathlib import Path

REQUIRED = ["## 是什么", "## 为什么重要", "## 常见误区", "## 在本工作台中的用法", "## 一句话总结"]


def test_foundations_have_required_sections_and_no_markers(project_root: Path) -> None:
    import re

    foundations = sorted((project_root / "shared/knowledge/foundations").glob("*.md"))
    assert len(foundations) >= 11, "expected at least 11 foundation docs"
    markers = re.compile(r"TODO|TBD|FIXME|待定")
    for path in foundations:
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{path.name} missing {heading}"
        assert len(text.strip()) > 200, f"{path.name} too short"
        assert not markers.search(text), f"{path.name} contains unfinished marker"
