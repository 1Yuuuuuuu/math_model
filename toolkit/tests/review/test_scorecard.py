from __future__ import annotations

import math
from pathlib import Path

import pytest

from cumcm_toolkit.review.engine import load_rubric
from cumcm_toolkit.review.scorecard import evaluate_scorecard


ROOT = Path(__file__).resolve().parents[3]


def _rubric(name: str = "model-quality") -> dict:
    return load_rubric(ROOT / "shared/rubrics" / f"{name}.yaml")


def _submitted(rubric: dict, score: float = 85.0) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": dimension["dimension_id"],
            "score": score,
            "rationale": f"Evidence-backed assessment for {dimension['dimension_id']}",
            "evidence_refs": ["clm_score_evidence"],
        }
        for dimension in rubric["scoring"]["dimensions"]
    ]


def test_model_and_paper_rubrics_use_approved_weights() -> None:
    model = _rubric("model-quality")["scoring"]
    paper = _rubric("paper-quality")["scoring"]
    assert model["threshold"] == paper["threshold"] == 85
    assert model["dimension_floor"] == paper["dimension_floor"] == 70
    assert [item["weight"] for item in model["dimensions"]] == [15, 20, 15, 10, 20, 20]
    assert [item["weight"] for item in paper["dimensions"]] == [25, 15, 20, 15, 10, 10, 5]


def test_scorecard_recomputes_boundary_and_does_not_trust_total() -> None:
    rubric = _rubric()
    result = evaluate_scorecard(rubric, _submitted(rubric, 85.0))
    assert result["weighted_total"] == pytest.approx(85.0)
    assert result["passed"] is True
    assert all(item["weighted_points"] > 0 for item in result["dimensions"])


def test_total_or_dimension_below_threshold_fails() -> None:
    rubric = _rubric()
    below_total = evaluate_scorecard(rubric, _submitted(rubric, 84.9))
    assert below_total["passed"] is False

    one_low = _submitted(rubric, 90.0)
    one_low[0]["score"] = 69.9
    result = evaluate_scorecard(rubric, one_low)
    assert result["weighted_total"] >= 85
    assert result["passed"] is False


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_scorecard_rejects_dimension_identity_drift(mutation: str) -> None:
    rubric = _rubric()
    submitted = _submitted(rubric)
    if mutation == "missing":
        submitted.pop()
    elif mutation == "duplicate":
        submitted[-1]["dimension_id"] = submitted[0]["dimension_id"]
    else:
        submitted[-1]["dimension_id"] = "unknown-dimension"
    with pytest.raises(ValueError, match="dimension"):
        evaluate_scorecard(rubric, submitted)


@pytest.mark.parametrize("score", [-0.1, 100.1, math.nan, math.inf])
def test_scorecard_rejects_invalid_scores(score: float) -> None:
    rubric = _rubric()
    submitted = _submitted(rubric)
    submitted[0]["score"] = score
    with pytest.raises(ValueError, match="score"):
        evaluate_scorecard(rubric, submitted)


@pytest.mark.parametrize("field,value", [("rationale", ""), ("evidence_refs", [])])
def test_scorecard_requires_rationale_and_claim_evidence(field: str, value: object) -> None:
    rubric = _rubric()
    submitted = _submitted(rubric)
    submitted[0][field] = value
    with pytest.raises(ValueError, match=field):
        evaluate_scorecard(rubric, submitted)


def test_rubric_rejects_weights_that_do_not_sum_to_100() -> None:
    rubric = _rubric()
    rubric["scoring"]["dimensions"][0]["weight"] = 14
    with pytest.raises(ValueError, match="weights"):
        evaluate_scorecard(rubric, _submitted(_rubric()))
