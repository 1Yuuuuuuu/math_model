from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_contracts import load_json, make_validator


VALID_SOURCE_FIXTURES = (
    "literature-source.json",
    "literature-source-user-provided-offline.json",
    "literature-source-candidate.json",
    "literature-source-rejected.json",
)

APPROVED_INVALID_FIXTURES = (
    ("literature-source-approved-without-decision.json", (), "required"),
    ("literature-source-approved-empty-artifacts.json", ("artifact_ids",), "minItems"),
    ("literature-source-approved-null-hash.json", ("content_sha256",), "type"),
    ("literature-source-approved-invalid-hash.json", ("content_sha256",), "oneOf"),
)


@pytest.mark.parametrize("fixture_name", VALID_SOURCE_FIXTURES)
def test_literature_source_accepts_all_lifecycle_states_and_offline_user_input(
    project_root: Path, fixture_name: str
) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    fixture = load_json(
        project_root / f"shared/fixtures/contracts/valid/{fixture_name}"
    )

    assert list(validator.iter_errors(fixture)) == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_path", "expected_validator"),
    APPROVED_INVALID_FIXTURES,
)
def test_approved_literature_source_requires_every_approval_artifact(
    project_root: Path,
    fixture_name: str,
    expected_path: tuple[object, ...],
    expected_validator: str,
) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    invalid = load_json(
        project_root / f"shared/fixtures/contracts/invalid/{fixture_name}"
    )

    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == expected_path
    assert errors[0].validator == expected_validator


@pytest.mark.parametrize(
    "fixture_name",
    (
        "literature-source-paper-search-null-url.json",
        "literature-source-runtime-search-invalid-url.json",
        "literature-source-timezone-less.json",
    ),
)
def test_search_urls_and_retrieval_times_fail_closed(
    project_root: Path, fixture_name: str
) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    invalid = load_json(
        project_root / f"shared/fixtures/contracts/invalid/{fixture_name}"
    )

    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1


@pytest.mark.parametrize("backend", ("paper-search", "runtime-search"))
def test_search_backends_require_cumcm_http_urls(
    project_root: Path, backend: str
) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    fixture = deepcopy(
        load_json(project_root / "shared/fixtures/contracts/valid/literature-source.json")
    )
    fixture["retrieval_backend"] = backend

    fixture["canonical_url"] = None
    assert list(validator.iter_errors(fixture))

    fixture["canonical_url"] = "ftp://example.invalid/not-http"
    assert list(validator.iter_errors(fixture))

    fixture["canonical_url"] = "https://example.invalid/synthetic-method"
    assert list(validator.iter_errors(fixture)) == []
