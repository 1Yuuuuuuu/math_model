from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cumcm_toolkit.review.engine import load_rubric, review


ROOT = Path(__file__).resolve().parents[2]


def _scores(rubric: dict[str, object], score: float = 90) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": item["dimension_id"],
            "score": score,
            "rationale": f"Evidence for {item['dimension_id']}",
            "evidence_refs": ["clm_model_review"],
        }
        for item in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def test_model_gate_is_isolated_and_does_not_modify_sources(tmp_path: Path) -> None:
    artifact_root = tmp_path / "phase3"
    artifact_root.mkdir()
    inputs = {
        "problem_analysis": {"status": "complete"},
        "data_audit": {"status": "complete"},
        "model_selection": {
            "status": "complete",
            "baseline": "",
            "candidate_comparison": [],
            "validation_plan": {"metric": "rmse"},
        },
        "solver_run": {"status": "complete", "experiment_id": "exp_review_001"},
        "sensitivity_report": {"status": "complete"},
        "evidence_refs": ["clm_model_review"],
        "evidence_index": {
            "clm_model_review": {"claim_id": "clm_model_review"},
        },
    }
    (artifact_root / "handoffs.json").write_text(
        json.dumps(inputs, sort_keys=True), encoding="utf-8"
    )
    before = _hash_tree(artifact_root)
    rubric = load_rubric(ROOT / "shared/rubrics/model-quality.yaml")
    report = review(
        inputs,
        rubric,
        reviewed_at="2026-08-25T12:00:00+08:00",
        reviewed_files=[artifact_root / "handoffs.json"],
        file_root=artifact_root,
        score_dimensions=_scores(rubric),
    )
    after = _hash_tree(artifact_root)

    assert before == after
    assert report["reviewed_files"][0]["path"] == "handoffs.json"
    assert report["evaluated_rule_ids"] == [
        "model_baseline_present",
        "model_candidates_compared",
        "model_validation_planned",
        "model_sensitivity_complete",
    ]
    assert {item["finding_id"] for item in report["findings"]} == {
        "finding_model_baseline_present",
        "finding_model_candidates_compared",
    }
    assert all(item["review_gate"] == "model" for item in report["findings"])
