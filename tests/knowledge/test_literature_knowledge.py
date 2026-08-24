import re
import unicodedata
from pathlib import Path


def _normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title.lower())
    return re.sub(r"[\W_]+", "", text)


def group_candidates(records: list[dict]) -> dict[str, list[str]]:
    """参考实现：按 DOI → 规范化标题 → 规范化 URL 的顺序形成确定性分组。"""
    groups: dict[str, list[str]] = {}
    for record in records:
        key = None
        if record.get("doi"):
            key = f"doi:{record['doi'].lower()}"
        elif record.get("title"):
            key = f"title:{_normalize_title(record['title'])}"
        elif record.get("url"):
            key = f"url:{re.sub(r'#.*$', '', record['url']).rstrip('/')}"
        if key is None:
            continue
        groups.setdefault(key, []).append(record["id"])
    return groups


def read_doc(project_root: Path, name: str) -> str:
    return (project_root / "shared" / "knowledge" / "literature" / name).read_text(encoding="utf-8")


def test_dedup_groups_by_doi() -> None:
    groups = group_candidates(
        [
            {"id": "a", "doi": "10.1000/ABC"},
            {"id": "b", "doi": "10.1000/abc"},
            {"id": "c", "doi": "10.1000/XYZ"},
        ]
    )
    assert set(groups["doi:10.1000/abc"]) == {"a", "b"}


def test_dedup_groups_by_normalized_title() -> None:
    groups = group_candidates(
        [
            {"id": "a", "title": "A Novel Method"},
            {"id": "b", "title": "A  Novel  Method!"},
            {"id": "c", "title": "A Different Method"},
        ]
    )
    assert set(groups["title:anovelmethod"]) == {"a", "b"}


def test_dedup_marks_conflicts_for_human_review(project_root: Path) -> None:
    doc = read_doc(project_root, "deduplication.md")
    assert "人工核验" in doc or "人工" in doc
    assert "不得静默合并" in doc or "不能静默合并" in doc


def test_source_evaluation_rejects_citation_count_as_quality(project_root: Path) -> None:
    doc = read_doc(project_root, "source-evaluation.md")
    assert "引用量" in doc and "期刊等级" in doc
    assert "不等同" in doc or "不能等同于" in doc


def test_search_strategy_covers_candidate_usage(project_root: Path) -> None:
    doc = read_doc(project_root, "search-strategy.md")
    for phrase in ("检索问题", "关键词", "候选", "正式引用"):
        assert phrase in doc
