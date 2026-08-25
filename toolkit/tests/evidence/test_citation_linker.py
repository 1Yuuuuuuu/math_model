import pytest

from cumcm_toolkit.evidence.citation_linker import (
    approved_sources,
    link_approved_source,
    link_citation,
)
from scripts.validate_contracts import load_json, make_validator


def _approved_source() -> dict:
    return {
        "schema_version": "1.0",
        "source_id": "src_synthetic_method",
        "title": "示例方法",
        "authors": ["甲", "乙"],
        "year": 2024,
        "venue_or_repository": "合成仓库",
        "identifiers": {},
        "canonical_url": "https://example.invalid/method",
        "retrieved_at": "2026-08-22T00:00:00+00:00",
        "retrieval_backend": "user-provided",
        "verification_status": "approved",
        "artifact_ids": ["art_method_note"],
        "content_sha256": "a" * 64,
        "decision_id": "dec_outline_sources",
    }


def test_link_citation_validates_against_phase0a_schema(project_root: pytest.FixtureRequest) -> None:
    record = link_citation(
        citation_id="cite_synthetic_method",
        claim_id="clm_method_choice",
        source_id="src_synthetic_method",
        usage="method",
        locator={"kind": "paragraph", "value": "第 2 段"},
        support_boundary="仅支持方法性主张",
        verified_at="2026-08-22T00:00:00+00:00",
    )
    schema = load_json(project_root / "shared/contracts/citation-link.schema.json")
    validator = make_validator(schema)
    assert list(validator.iter_errors(record)) == []


def test_link_approved_source_succeeds() -> None:
    record = link_approved_source(
        source_record=_approved_source(),
        claim_id="clm_method_choice",
        usage="method",
        locator={"kind": "paragraph", "value": "第 2 段"},
        support_boundary="仅支持方法性主张",
    )
    assert record["source_id"] == "src_synthetic_method"
    assert record["citation_id"].startswith("cite_")
    assert len(record["citation_id"]) == 5 + 24


def test_link_approved_source_rejects_unapproved() -> None:
    source = _approved_source()
    source["verification_status"] = "candidate"
    with pytest.raises(ValueError):
        link_approved_source(
            source_record=source, claim_id="clm_x", usage="method",
            locator={"kind": "paragraph", "value": "p"}, support_boundary="b",
        )


def test_link_approved_source_rejects_missing_decision() -> None:
    source = _approved_source()
    del source["decision_id"]
    with pytest.raises(ValueError):
        link_approved_source(
            source_record=source, claim_id="clm_x", usage="method",
            locator={"kind": "paragraph", "value": "p"}, support_boundary="b",
        )


def test_approved_sources_filters() -> None:
    approved = _approved_source()
    candidate = dict(approved, source_id="src_c", verification_status="candidate")
    rejected = dict(approved, source_id="src_r", verification_status="rejected", decision_id=None)
    result = approved_sources([approved, candidate, rejected])
    assert [s["source_id"] for s in result] == ["src_synthetic_method"]
