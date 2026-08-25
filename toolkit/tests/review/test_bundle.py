from __future__ import annotations

import copy
from pathlib import Path

from cumcm_toolkit.review.bundle import REVIEW_SLOTS, build_review_bundle
from cumcm_toolkit.review.engine import load_rubric, review


SHA = "a" * 64
CAPABILITIES = {
    "citation_check",
    "latex_lint",
    "latex_build",
    "pdf_inspect",
    "evidence_linker",
    "citation_linker",
}


def _scores(rubric: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": dimension["dimension_id"],
            "score": 90,
            "rationale": f"Assessment for {dimension['dimension_id']}",
            "evidence_refs": ["clm_review_current"],
        }
        for dimension in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def _materials(project_root: Path) -> tuple[dict, dict, dict, dict]:
    rubric_names = {
        "submission": "submission",
        "reproducibility": "reproducibility",
        "model": "model-quality",
        "paper": "paper-quality",
        "red_team": "red-team",
    }
    rubrics = {
        slot: load_rubric(project_root / "shared/rubrics" / f"{name}.yaml")
        for slot, name in rubric_names.items()
    }
    evidence = ["clm_review_current"]
    inputs = {
        "submission": {
            "submission_reports": {
                "build": {"status": "ok"},
                "lint": {"status": "ok"},
                "citations": {"status": "ok"},
                "pdf": {"status": "ok", "blank_pages": []},
                "source_hash": SHA,
                "pdf_hash": "b" * 64,
                "annual_rule_verified": True,
            },
            "evidence_refs": evidence,
        },
        "reproducibility": {
            "problem_analysis": {"status": "complete"},
            "data_audit": {"status": "complete"},
            "model_selection": {"status": "complete"},
            "solver_run": {
                "status": "complete",
                "experiment_id": "exp_solver_run",
                "experiment_status": "succeeded",
                "lock_sha256": SHA,
            },
            "sensitivity_report": {"status": "complete"},
            "artifact_index": {"art_result": {}},
            "experiment_index": {"exp_solver_run": {}},
            "evidence_index": {
                "clm_review_current": {"claim_id": "clm_review_current"}
            },
            "evidence_refs": evidence,
        },
        "model": {
            "model_selection": {
                "baseline": "mean predictor",
                "candidate_comparison": ["mean", "linear"],
                "validation_plan": {"metric": "rmse"},
            },
            "sensitivity_report": {"status": "complete"},
            "evidence_refs": evidence,
        },
        "paper": {
            "paper_reports": {
                "evidence": {"status": "ok", "unresolved": []},
                "citations": {"status": "ok"},
                "lint": {"status": "ok"},
            },
            "evidence_refs": evidence,
        },
        "red_team": {
            "paper_reports": {
                "key_claim_ids": evidence,
                "claim_boundaries": [{"claim_id": "clm_review_current"}],
                "limitations": ["Known limitation."],
                "challenges": [{"claim_id": "clm_review_current"}],
            },
            "evidence_refs": evidence,
        },
    }
    evidence_index = {
        "clm_review_current": {"claim_id": "clm_review_current"}
    }
    for review_inputs in inputs.values():
        review_inputs["evidence_index"] = copy.deepcopy(evidence_index)
    score_dimensions = {
        "model": _scores(rubrics["model"]),
        "paper": _scores(rubrics["paper"]),
    }
    reports = {
        slot: review(
            inputs[slot],
            rubrics[slot],
            capabilities=CAPABILITIES,
            score_dimensions=score_dimensions.get(slot),
            reviewed_at="2026-08-25T12:00:00+08:00",
        )
        for slot in REVIEW_SLOTS
    }
    return reports, inputs, rubrics, score_dimensions


def _bundle(project_root: Path, tmp_path: Path, **changes: object) -> dict[str, object]:
    reports, inputs, rubrics, scores = _materials(project_root)
    kwargs = {
        "reports": reports,
        "current_inputs": inputs,
        "rubrics": rubrics,
        "reviewed_files": {slot: [] for slot in REVIEW_SLOTS},
        "reviewed_artifact_ids": ["art_final_paper"],
        "file_root": tmp_path,
        "score_dimensions": scores,
        "created_at": "2026-08-25T13:00:00+08:00",
    }
    kwargs.update(changes)
    return build_review_bundle(**kwargs)


def test_five_current_passed_reports_are_ready(project_root: Path, tmp_path: Path) -> None:
    bundle = _bundle(project_root, tmp_path)
    assert bundle["readiness"] == "ready_for_phase_6"
    assert bundle["reviewed_artifact_ids"] == ["art_final_paper"]
    assert bundle["errors"] == []
    assert set(bundle["report_ids"]) == set(REVIEW_SLOTS)  # type: ignore[arg-type]


def test_missing_report_is_blocked_with_null_slot(project_root: Path, tmp_path: Path) -> None:
    reports, inputs, rubrics, scores = _materials(project_root)
    reports.pop("paper")
    bundle = build_review_bundle(
        reports=reports,
        current_inputs=inputs,
        rubrics=rubrics,
        reviewed_files={slot: [] for slot in REVIEW_SLOTS},
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=scores,
    )
    assert bundle["readiness"] == "blocked"
    assert bundle["report_ids"]["paper"] is None  # type: ignore[index]


def test_stale_or_failed_report_is_not_ready(project_root: Path, tmp_path: Path) -> None:
    reports, inputs, rubrics, scores = _materials(project_root)
    changed_inputs = copy.deepcopy(inputs)
    changed_inputs["red_team"]["paper_reports"]["limitations"].append("New limit.")
    stale = build_review_bundle(
        reports=reports,
        current_inputs=changed_inputs,
        rubrics=rubrics,
        reviewed_files={slot: [] for slot in REVIEW_SLOTS},
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=scores,
    )
    assert stale["readiness"] == "not_ready"

    failed_inputs = copy.deepcopy(inputs)
    failed_inputs["submission"]["submission_reports"]["build"]["status"] = "failed"
    reports["submission"] = review(
        failed_inputs["submission"],
        rubrics["submission"],
        capabilities=CAPABILITIES,
        reviewed_at="2026-08-25T12:00:00+08:00",
    )
    failed = build_review_bundle(
        reports=reports,
        current_inputs=failed_inputs,
        rubrics=rubrics,
        reviewed_files={slot: [] for slot in REVIEW_SLOTS},
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=scores,
    )
    assert failed["readiness"] == "not_ready"


def test_missing_score_material_is_blocked(project_root: Path, tmp_path: Path) -> None:
    bundle = _bundle(project_root, tmp_path, score_dimensions={})
    assert bundle["readiness"] == "blocked"
    assert "score" in " ".join(bundle["errors"]).lower()


def test_malformed_report_id_returns_blocked_bundle(project_root: Path, tmp_path: Path) -> None:
    reports, inputs, rubrics, scores = _materials(project_root)
    reports["paper"]["review_id"] = "review_not-a-digest"
    bundle = build_review_bundle(
        reports=reports,
        current_inputs=inputs,
        rubrics=rubrics,
        reviewed_files={slot: [] for slot in REVIEW_SLOTS},
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=scores,
    )
    assert bundle["readiness"] == "blocked"
    assert bundle["report_ids"]["paper"] is None  # type: ignore[index]
