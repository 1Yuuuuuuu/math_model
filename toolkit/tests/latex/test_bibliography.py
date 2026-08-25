import pytest

from cumcm_toolkit.latex.bibliography import bibtex_entry, generate_bibliography


def _approved_source(source_id: str = "src_synthetic_method", venue: str | None = "合成期刊") -> dict:
    return {
        "schema_version": "1.0",
        "source_id": source_id,
        "title": "示例方法",
        "authors": ["甲", "乙"],
        "year": 2024,
        "venue_or_repository": venue,
        "identifiers": {"doi": "10.1000/abc"},
        "canonical_url": "https://example.invalid/method",
        "retrieved_at": "2026-08-22T00:00:00+00:00",
        "retrieval_backend": "user-provided",
        "verification_status": "approved",
        "artifact_ids": ["art_method_note"],
        "content_sha256": "a" * 64,
        "decision_id": "dec_outline_sources",
    }


def test_bibtex_entry_article_with_fields() -> None:
    entry = bibtex_entry(_approved_source())
    assert entry.startswith("@article{src_")
    assert "title" in entry and "示例方法" in entry
    assert "author" in entry and "甲" in entry
    assert "year" in entry and "2024" in entry
    assert "journal" in entry and "合成期刊" in entry
    assert "doi" in entry and "10.1000/abc" in entry
    assert "url" in entry


def test_bibtex_entry_misc_without_venue() -> None:
    entry = bibtex_entry(_approved_source(venue=None))
    assert entry.startswith("@misc{src_")
    assert "journal" not in entry


def test_generate_bibliography_deterministic_and_sorted() -> None:
    sources = [_approved_source("src_b"), _approved_source("src_a")]
    first = generate_bibliography(sources)
    second = generate_bibliography(list(reversed(sources)))
    assert first == second
    entry_a = bibtex_entry(_approved_source("src_a"))
    entry_b = bibtex_entry(_approved_source("src_b"))
    assert first.index(entry_a) < first.index(entry_b)
