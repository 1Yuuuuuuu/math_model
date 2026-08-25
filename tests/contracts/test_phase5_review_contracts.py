from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_contracts import load_json, make_validator


EXPECTED = {
    "modeling-handoff": (
        "modeling-handoff.json",
        "modeling-handoff-complete-empty-output.json",
    ),
    "review-report": ("review-report.json", "review-report-invalid-status.json"),
    "review-bundle": ("review-bundle.json", "review-bundle-missing-gate.json"),
}


def _validator(project_root: Path, contract_id: str):
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    entry = next(item for item in catalog["contracts"] if item["id"] == contract_id)
    return make_validator(load_json(project_root / entry["schema"]))


def test_phase5_contracts_are_registered_and_have_positive_negative_fixtures(
    project_root: Path,
) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    assert len(catalog["contracts"]) == 15
    assert set(EXPECTED).issubset({item["id"] for item in catalog["contracts"]})

    for contract_id, (valid_name, invalid_name) in EXPECTED.items():
        validator = _validator(project_root, contract_id)
        valid = load_json(project_root / "shared/fixtures/contracts/valid" / valid_name)
        invalid = load_json(project_root / "shared/fixtures/contracts/invalid" / invalid_name)
        assert list(validator.iter_errors(valid)) == []
        assert list(validator.iter_errors(invalid)), contract_id


def test_modeling_handoff_conditional_envelope_rejects_mixed_states(
    project_root: Path,
) -> None:
    validator = _validator(project_root, "modeling-handoff")
    complete = load_json(
        project_root / "shared/fixtures/contracts/valid/modeling-handoff.json"
    )

    blocked_with_output = dict(complete)
    blocked_with_output["status"] = "blocked"
    blocked_with_output["missing_inputs"] = ["paper source"]
    blocked_with_output["failed_step"] = "load paper"
    blocked_with_output["resume_when"] = ["provide paper source"]
    assert list(validator.iter_errors(blocked_with_output))

    complete_without_output = dict(complete)
    complete_without_output["outputs"] = []
    assert list(validator.iter_errors(complete_without_output))


def test_review_report_resolves_review_finding_offline(project_root: Path) -> None:
    validator = _validator(project_root, "review-report")
    report = load_json(
        project_root / "shared/fixtures/contracts/valid/review-report.json"
    )
    finding = load_json(
        project_root / "shared/fixtures/contracts/valid/review-finding.json"
    )
    report["findings"] = [finding]
    report["status"] = "failed"
    assert list(validator.iter_errors(report)) == []


@pytest.mark.parametrize(
    "artifact_type",
    ["repro-review", "paper-review", "red-team-review", "submission-audit"],
)
def test_modeling_handoff_accepts_every_phase5_reviewer_artifact_type(
    project_root: Path, artifact_type: str
) -> None:
    validator = _validator(project_root, "modeling-handoff")
    payload = load_json(project_root / "shared/fixtures/contracts/valid/modeling-handoff.json")
    payload["artifact_type"] = artifact_type
    assert list(validator.iter_errors(payload)) == []
