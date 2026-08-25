from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from cumcm_toolkit.review.engine import (
    _report_validator,
    canonical_digest,
    is_review_current,
    load_rubric,
    review,
)


def _valid_inputs() -> dict[str, object]:
    return {
        "problem_analysis": {"status": "complete"},
        "data_audit": {"status": "complete"},
        "model_selection": {
            "status": "complete",
            "baseline": "mean predictor",
            "candidate_comparison": ["linear-regression", "mean predictor"],
            "validation_plan": {"metric": "rmse", "split": "time-aware"},
        },
        "solver_run": {"status": "complete", "experiment_id": "exp_linear_001"},
        "sensitivity_report": {"status": "complete", "parameters": {"slope": [2.7, 3.0, 3.3]}},
        "evidence_refs": ["clm_model_review"],
        "evidence_index": {
            "clm_model_review": {"claim_id": "clm_model_review"},
        },
    }


def _valid_scores(rubric: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": dimension["dimension_id"],
            "score": 90,
            "rationale": f"Evidence-backed assessment for {dimension['dimension_id']}",
            "evidence_refs": ["clm_model_review"],
        }
        for dimension in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def test_canonical_digest_is_order_independent_and_rejects_nan() -> None:
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})
    assert len(canonical_digest({"a": 1})) == 64
    with pytest.raises(ValueError, match="canonical JSON"):
        canonical_digest({"bad": float("nan")})


def test_load_rubric_rejects_unregistered_checker(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text(
        """rubric_id: unsafe\nversion: \"1.0\"\nreview_gate: model\nrequires_capabilities: []\nrules:\n  - rule_id: unsafe_rule\n    severity: S1\n    checker: python_eval\n    params: {}\n    summary: Unsafe.\n    evidence_paths: [evidence_refs]\n    recommendation: Remove it.\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unregistered checker"):
        load_rubric(path)


def test_valid_model_review_passes_and_is_current(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    inputs = _valid_inputs()
    scores = _valid_scores(rubric)
    report = review(
        inputs,
        rubric,
        reviewed_at="2026-08-25T12:00:00+08:00",
        score_dimensions=scores,
    )
    assert report["status"] == "passed"
    assert report["findings"] == []
    assert report["errors"] == []
    assert is_review_current(report, inputs, rubric, score_dimensions=scores)
    assert len(report["rubric_digest"]) == 64
    report_schema = json.loads(
        (project_root / "shared/contracts/review-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator(
        report_schema, format_checker=jsonschema.FormatChecker()
    ).validate(report)


def test_review_report_validator_rejects_nonfinite_scorecard_number(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    report = review(
        _valid_inputs(),
        rubric,
        reviewed_at="2026-08-25T12:00:00+08:00",
        score_dimensions=_valid_scores(rubric),
    )
    report["scorecard"]["weighted_total"] = float("nan")  # type: ignore[index]

    errors = list(_report_validator().iter_errors(report))

    assert [(tuple(error.absolute_path), error.validator) for error in errors] == [
        (("scorecard", "weighted_total"), "type")
    ]


def test_s1_failure_emits_contract_valid_finding(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    inputs = _valid_inputs()
    inputs["model_selection"]["baseline"] = ""  # type: ignore[index]
    report = review(
        inputs,
        rubric,
        reviewed_at="2026-08-25T12:00:00+08:00",
        score_dimensions=_valid_scores(rubric),
    )
    assert report["status"] == "failed"
    finding = next(item for item in report["findings"] if item["finding_id"] == "finding_model_baseline_present")
    schema = json.loads(
        (project_root / "shared/contracts/review-finding.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(finding)
    assert finding["severity"] == "S1"
    assert finding["evidence_refs"] == ["clm_model_review"]
    assert finding["recommendation"]


def test_missing_evidence_or_capability_blocks(project_root: Path) -> None:
    model = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    without_evidence = _valid_inputs()
    without_evidence["evidence_refs"] = []
    report = review(without_evidence, model)
    assert report["status"] == "blocked"
    assert "evidence" in " ".join(report["errors"]).lower()

    paper = load_rubric(project_root / "shared/rubrics/paper-quality.yaml")
    report = review(_valid_inputs(), paper, capabilities={"evidence_linker"})
    assert report["status"] == "blocked"
    assert "citation_check" in " ".join(report["errors"])


def test_changed_input_invalidates_old_review(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    original = _valid_inputs()
    report = review(original, rubric)
    changed = copy.deepcopy(original)
    changed["model_selection"]["validation_plan"]["metric"] = "mae"  # type: ignore[index]
    assert not is_review_current(report, changed, rubric)
    replacement = review(changed, rubric)
    assert replacement["review_id"] != report["review_id"]


def test_all_present_rejects_empty_handoff(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/reproducibility.yaml")
    inputs = _valid_inputs()
    inputs["problem_analysis"] = {}
    report = review(inputs, rubric)
    finding_ids = {item["finding_id"] for item in report["findings"]}
    assert "finding_repro_handoffs_present" in finding_ids


def test_rubric_change_invalidates_old_review(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    inputs = _valid_inputs()
    report = review(inputs, rubric)
    changed = copy.deepcopy(rubric)
    changed["rules"][0]["summary"] = "Changed review meaning."
    assert not is_review_current(report, inputs, changed)
    replacement = review(inputs, changed)
    assert replacement["review_id"] != report["review_id"]


def test_reviewed_file_change_invalidates_old_review(project_root: Path, tmp_path: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    source = tmp_path / "model-selection.json"
    source.write_text('{"version": 1}', encoding="utf-8")
    inputs = _valid_inputs()
    report = review(inputs, rubric, reviewed_files=[source], file_root=tmp_path)
    assert is_review_current(
        report, inputs, rubric, reviewed_files=[source], file_root=tmp_path
    )
    source.write_text('{"version": 2}', encoding="utf-8")
    assert not is_review_current(
        report, inputs, rubric, reviewed_files=[source], file_root=tmp_path
    )


def test_invalid_review_timestamp_is_rejected(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    with pytest.raises(ValueError, match="RFC 3339"):
        review(_valid_inputs(), rubric, reviewed_at="not-a-date")


def test_checker_parameters_are_validated_when_rubric_loads(tmp_path: Path) -> None:
    path = tmp_path / "bad-params.yaml"
    path.write_text(
        """rubric_id: bad-params\nversion: \"1.0\"\nreview_gate: model\nrequires_capabilities: []\nrules:\n  - rule_id: bad_params_rule\n    severity: S1\n    checker: equals\n    params: {}\n    summary: Missing parameters.\n    evidence_paths: [evidence_refs]\n    recommendation: Add parameters.\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="checker params"):
        load_rubric(path)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text(
        """rubric_id: duplicate\nrubric_id: shadowed\nversion: \"1.0\"\nreview_gate: model\nrequires_capabilities: []\nrules: []\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_rubric(path)


@pytest.mark.parametrize(
    "handoff_key",
    ["problem_analysis", "data_audit", "model_selection", "solver_run", "sensitivity_report"],
)
def test_reproducibility_rejects_every_blocked_handoff(
    project_root: Path, handoff_key: str
) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/reproducibility.yaml")
    inputs = _valid_inputs()
    inputs[handoff_key]["status"] = "blocked"  # type: ignore[index]
    report = review(inputs, rubric)
    assert report["status"] == "failed"
    assert any(handoff_key.split("_")[0] in item["finding_id"] for item in report["findings"])
