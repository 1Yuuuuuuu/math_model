from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts.contract_formats import FORMAT_CHECKER
from scripts.validate_contracts import load_json, make_validator


NAMED_INVALID_EXPECTATIONS = {
    "shared/fixtures/contracts/invalid/error-missing-code.json": ((), "required"),
    "shared/fixtures/contracts/invalid/artifact-absolute-path.json": (("path",), "pattern"),
    "shared/fixtures/contracts/invalid/artifact-parent-traversal.json": (("path",), "pattern"),
    "shared/fixtures/contracts/invalid/artifact-linebreak-traversal.json": (("path",), "pattern"),
    "shared/fixtures/contracts/invalid/experiment-missing-input.json": (("input_artifact_ids",), "minItems"),
    "shared/fixtures/contracts/invalid/experiment-timezone-less.json": (("started_at",), "format"),
    "shared/fixtures/contracts/invalid/experiment-linebreak-time.json": (("started_at",), "format"),
    "shared/fixtures/contracts/invalid/evidence-link-missing-boundary.json": ((), "required"),
    "shared/fixtures/contracts/invalid/decision-nonhuman.json": (("decided_by",), "const"),
    "shared/fixtures/contracts/invalid/workflow-state-skipped-gate.json": (("gates", "gate_1_problem"), "const"),
    "shared/fixtures/contracts/invalid/review-finding-bad-severity.json": (("severity",), "enum"),
    "shared/fixtures/contracts/invalid/annual-rule-missing-source.json": ((), "required"),
    "shared/fixtures/contracts/invalid/annual-rule-empty-host.json": (("source_url",), "format"),
    "shared/fixtures/contracts/invalid/annual-rule-invalid-source-url.json": (("source_url",), "format"),
    "shared/fixtures/contracts/invalid/annual-rule-invalid-ipv6-colons.json": (("source_url",), "format"),
    "shared/fixtures/contracts/invalid/annual-rule-invalid-ipv6-nine-segments.json": (("source_url",), "format"),
    "shared/fixtures/contracts/invalid/annual-rule-timezone-less.json": (("verified_at",), "format"),
    "shared/fixtures/contracts/invalid/annual-rule-userinfo-empty-host.json": (("source_url",), "format"),
    "shared/fixtures/contracts/invalid/asset-manifest-duplicate-target.json": (("assets", 0, "package_targets"), "uniqueItems"),
}


def test_catalog_examples_match_their_schemas(project_root) -> None:
    catalog_path = project_root / "shared/contracts/catalog.json"
    catalog = load_json(catalog_path)

    for entry in catalog["contracts"]:
        schema = load_json(project_root / entry["schema"])
        Draft202012Validator.check_schema(schema)
        validator = make_validator(schema)
        assert validator.format_checker is FORMAT_CHECKER

        for relative_path in entry["valid_examples"]:
            fixture = load_json(project_root / relative_path)
            validator.validate(fixture)

        for relative_path in entry["invalid_examples"]:
            fixture = load_json(project_root / relative_path)
            with pytest.raises(ValidationError):
                validator.validate(fixture)


def test_each_invalid_fixture_fails_once_for_its_named_rule(project_root: Path) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    catalog_invalid_paths = {
        relative_path
        for entry in catalog["contracts"]
        for relative_path in entry["invalid_examples"]
    }
    assert set(NAMED_INVALID_EXPECTATIONS) == catalog_invalid_paths

    for entry in catalog["contracts"]:
        schema = load_json(project_root / entry["schema"])
        validator = make_validator(schema)
        for relative_path in entry["invalid_examples"]:
            expected_path, expected_validator = NAMED_INVALID_EXPECTATIONS[relative_path]
            fixture = load_json(project_root / relative_path)
            errors = list(validator.iter_errors(fixture))

            assert len(errors) == 1, relative_path
            error = errors[0]
            assert tuple(error.absolute_path) == expected_path, relative_path
            assert error.validator == expected_validator, relative_path
