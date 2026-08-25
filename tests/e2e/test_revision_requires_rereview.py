from __future__ import annotations

import copy
from pathlib import Path

from cumcm_toolkit.review.engine import is_review_current, load_rubric, review


ROOT = Path(__file__).resolve().parents[2]


def _scores(rubric: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": item["dimension_id"],
            "score": 90,
            "rationale": f"Evidence for {item['dimension_id']}",
            "evidence_refs": ["clm_model_review"],
        }
        for item in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def test_any_reviewed_input_change_requires_a_new_review() -> None:
    inputs = {
        "model_selection": {
            "baseline": "mean",
            "candidate_comparison": ["mean", "linear-regression"],
            "validation_plan": {"metric": "rmse"},
        },
        "sensitivity_report": {"status": "complete"},
        "evidence_refs": ["clm_model_review"],
        "evidence_index": {
            "clm_model_review": {"claim_id": "clm_model_review"},
        },
    }
    rubric = load_rubric(ROOT / "shared/rubrics/model-quality.yaml")
    scores = _scores(rubric)
    old_report = review(
        inputs, rubric, reviewed_at="2026-08-25T12:00:00+08:00", score_dimensions=scores
    )
    assert is_review_current(old_report, inputs, rubric, score_dimensions=scores)

    revised = copy.deepcopy(inputs)
    revised["model_selection"]["validation_plan"]["metric"] = "mae"
    assert not is_review_current(old_report, revised, rubric, score_dimensions=scores)

    new_report = review(
        revised, rubric, reviewed_at="2026-08-25T12:05:00+08:00", score_dimensions=scores
    )
    assert is_review_current(new_report, revised, rubric, score_dimensions=scores)
    assert new_report["review_id"] != old_report["review_id"]
