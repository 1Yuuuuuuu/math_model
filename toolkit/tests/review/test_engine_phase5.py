from __future__ import annotations

import copy
from pathlib import Path

from cumcm_toolkit.review.engine import is_review_current, load_rubric, review


def _inputs() -> dict[str, object]:
    return {
        "model_selection": {
            "baseline": "mean predictor",
            "candidate_comparison": ["linear-regression", "mean predictor"],
            "validation_plan": {"metric": "rmse"},
        },
        "sensitivity_report": {"status": "complete"},
        "evidence_refs": ["clm_model_review", "clm_external_review"],
        "evidence_index": {
            "clm_model_review": {"claim_id": "clm_model_review"},
            "clm_external_review": {"claim_id": "clm_external_review"},
        },
    }


def _scores(rubric: dict[str, object], score: float = 90.0) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": item["dimension_id"],
            "score": score,
            "rationale": f"Assessment for {item['dimension_id']}",
            "evidence_refs": ["clm_model_review"],
        }
        for item in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def test_scored_rubric_without_dimensions_is_blocked(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    report = review(_inputs(), rubric, reviewed_at="2026-08-25T12:00:00+08:00")
    assert report["status"] == "blocked"
    assert report["scorecard"] is None
    assert "score" in " ".join(report["errors"]).lower()


def test_scorecard_is_embedded_and_failure_emits_engine_owned_finding(
    project_root: Path,
) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    scores = _scores(rubric, 90)
    scores[0]["score"] = 69
    report = review(_inputs(), rubric, score_dimensions=scores)
    assert report["scorecard"]["passed"] is False  # type: ignore[index]
    finding = next(
        item for item in report["findings"] if item["finding_id"] == "finding_model_score_threshold"
    )
    assert finding["severity"] == "S1"
    assert report["status"] == "failed"


def test_external_finding_must_be_open_unique_and_use_current_evidence(
    project_root: Path,
) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    finding = {
        "schema_version": "1.0",
        "finding_id": "finding_external_reasoning_gap",
        "review_gate": "model",
        "severity": "S2",
        "summary": "Reasoning gap.",
        "evidence_refs": ["clm_external_review"],
        "recommendation": "Explain the transition.",
        "status": "open",
    }
    report = review(
        _inputs(), rubric, score_dimensions=_scores(rubric), reviewer_findings=[finding]
    )
    assert finding in report["findings"]
    assert report["status"] == "passed"

    resolved = copy.deepcopy(finding)
    resolved["status"] = "resolved"
    blocked = review(
        _inputs(), rubric, score_dimensions=_scores(rubric), reviewer_findings=[resolved]
    )
    assert blocked["status"] == "blocked"

    stale = copy.deepcopy(finding)
    stale["evidence_refs"] = ["clm_not_current"]
    blocked = review(
        _inputs(), rubric, score_dimensions=_scores(rubric), reviewer_findings=[stale]
    )
    assert blocked["status"] == "blocked"

    blocked = review(
        _inputs(),
        rubric,
        score_dimensions=_scores(rubric),
        reviewer_findings=[finding, finding],
    )
    assert blocked["status"] == "blocked"


def test_scores_and_external_findings_participate_in_review_currentness(
    project_root: Path,
) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    scores = _scores(rubric)
    report = review(_inputs(), rubric, score_dimensions=scores)
    assert is_review_current(report, _inputs(), rubric, score_dimensions=scores)
    changed = copy.deepcopy(scores)
    changed[0]["score"] = 89
    assert not is_review_current(report, _inputs(), rubric, score_dimensions=changed)


def test_generated_report_validates_formal_contract(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    report = review(_inputs(), rubric, score_dimensions=_scores(rubric))
    assert report["schema_version"] == "1.0"
    assert report["status"] == "passed"


def test_score_evidence_must_exist_in_current_inputs(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    scores = _scores(rubric)
    scores[0]["evidence_refs"] = ["clm_fabricated_score"]
    report = review(_inputs(), rubric, score_dimensions=scores)
    assert report["status"] == "blocked"
    assert "score evidence" in " ".join(report["errors"]).lower()


def test_root_evidence_must_resolve_in_evidence_index(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    inputs = _inputs()
    inputs["evidence_refs"] = ["clm_format_only"]
    scores = _scores(rubric)
    for score in scores:
        score["evidence_refs"] = ["clm_format_only"]
    report = review(inputs, rubric, score_dimensions=scores)
    assert report["status"] == "blocked"
    assert "unresolved evidence" in " ".join(report["errors"]).lower()


def test_red_team_requires_a_challenge_for_every_key_claim(project_root: Path) -> None:
    rubric = load_rubric(project_root / "shared/rubrics/red-team.yaml")
    inputs = {
        "paper_reports": {
            "key_claim_ids": ["clm_first_claim", "clm_second_claim"],
            "claim_boundaries": [
                {"claim_id": "clm_first_claim"},
                {"claim_id": "clm_second_claim"},
            ],
            "limitations": ["Known limitation."],
            "challenges": [{"claim_id": "clm_first_claim", "challenge": "Probe it."}],
        },
        "evidence_refs": ["clm_first_claim", "clm_second_claim"],
        "evidence_index": {
            "clm_first_claim": {"claim_id": "clm_first_claim"},
            "clm_second_claim": {"claim_id": "clm_second_claim"},
        },
    }
    report = review(
        inputs,
        rubric,
        capabilities={"evidence_linker", "citation_linker", "citation_check"},
    )
    assert report["status"] == "failed"
    assert any(item["finding_id"] == "finding_red_team_claims_challenged" for item in report["findings"])
