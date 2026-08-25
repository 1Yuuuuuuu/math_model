from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cumcm_toolkit.review.engine import canonical_digest
from cumcm_toolkit.workflow.actions import next_action
from cumcm_toolkit.workflow.config import load_workflow_config
from cumcm_toolkit.workflow.events import create_event
from cumcm_toolkit.workflow.state import replay_workflow


ROOT = Path(__file__).resolve().parents[3]


def _append(history: list[dict[str, object]], event_type: str, stage: str, **kwargs: object) -> None:
    occurred_at = (
        datetime(2026, 9, 10, 8, tzinfo=timezone(timedelta(hours=8)))
        + timedelta(minutes=len(history))
    ).isoformat()
    event = create_event(
        workspace_id="ws_competition_2026",
        event_type=event_type,
        stage=stage,
        occurred_at=occurred_at,
        history=history,
        **kwargs,
    )
    history.append(event)


def _start() -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    _append(history, "workspace_started", "intake")
    return history


def _children(history: list[dict[str, object]], stage: str) -> None:
    routes = {
        "intake": (("problem-reader", "art_problem_child"), ("data-auditor", "art_data_child")),
        "model_design": (("model-selector", "art_model_child"),),
        "solve": (("solver", "art_solver_child"), ("sensitivity-analyst", "art_sensitivity_child")),
        "review": (
            ("submission-auditor", "art_review_submission"),
            ("repro-reviewer", "art_review_repro"),
            ("model-reviewer", "art_review_model"),
            ("paper-reviewer", "art_review_paper"),
            ("red-team-reviewer", "art_review_red_team"),
        ),
    }
    for skill, artifact in routes[stage]:
        _append(history, "child_completed", stage, skill=skill, artifact_ids=[artifact])


def _decision(gate: str, decision_id: str, artifacts: list[str], outcome: str = "approved") -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "decision_id": decision_id,
        "gate": gate,
        "outcome": outcome,
        "selected_option": f"human choice for {gate}",
        "rationale": "Human reviewed the frozen artifacts.",
        "artifact_ids": artifacts,
        "decided_by": "human",
        "decided_at": "2026-09-10T10:00:00+08:00",
    }


def _ready_bundle() -> dict[str, object]:
    import json

    return json.loads(
        (ROOT / "shared/fixtures/contracts/valid/review-bundle.json").read_text(
            encoding="utf-8"
        )
    )


def test_complete_flow_stops_at_all_four_gates_and_reaches_complete() -> None:
    history = _start()
    decisions: list[dict[str, object]] = []

    _children(history, "intake")
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem_analysis"])
    snapshot = replay_workflow(history)
    assert snapshot["state"]["stage"] == "intake"
    assert snapshot["runtime_status"] == "waiting_human"
    assert snapshot["waiting_gate"] == "gate_1_problem"

    decisions.append(_decision("gate_1_problem", "dec_problem_approval", ["art_problem_analysis"]))
    _append(
        history,
        "gate_decided",
        "intake",
        gate="gate_1_problem",
        decision_id="dec_problem_approval",
        outcome="approved",
        artifact_ids=["art_problem_analysis"],
    )
    assert replay_workflow(history, decisions=decisions)["state"]["stage"] == "model_design"

    _children(history, "model_design")
    _append(history, "stage_completed", "model_design", artifact_ids=["art_model_plan"])
    decisions.append(_decision("gate_2_model", "dec_model_approval", ["art_model_plan"]))
    _append(
        history,
        "gate_decided",
        "model_design",
        gate="gate_2_model",
        decision_id="dec_model_approval",
        outcome="approved",
        artifact_ids=["art_model_plan"],
    )
    _append(history, "literature_branch_decided", "solve", literature_required=False)
    _children(history, "solve")
    _append(history, "stage_completed", "solve", artifact_ids=["art_solver_results"])
    assert replay_workflow(history, decisions=decisions)["state"]["stage"] == "outline"

    _append(history, "stage_completed", "outline", artifact_ids=["art_paper_outline"])
    decisions.append(_decision("gate_3_outline", "dec_outline_approval", ["art_paper_outline"]))
    _append(
        history,
        "gate_decided",
        "outline",
        gate="gate_3_outline",
        decision_id="dec_outline_approval",
        outcome="approved",
        artifact_ids=["art_paper_outline"],
    )
    _append(history, "stage_completed", "write", artifact_ids=["art_final_paper"])
    assert replay_workflow(history, decisions=decisions)["state"]["stage"] == "review"

    bundle = _ready_bundle()
    _children(history, "review")
    _append(
        history,
        "review_bundle_attached",
        "review",
        review_bundle_id=bundle["bundle_id"],
        artifact_ids=["art_final_paper"],
    )
    decisions.append(_decision("gate_4_submission", "dec_submission_approval", ["art_final_paper"]))
    _append(
        history,
        "gate_decided",
        "review",
        gate="gate_4_submission",
        decision_id="dec_submission_approval",
        outcome="approved",
        artifact_ids=["art_final_paper"],
    )
    assert replay_workflow(history, decisions=decisions, review_bundles=[bundle])["state"]["stage"] == "submission"

    _append(history, "submission_completed", "submission", artifact_ids=["art_submission_package"])
    final = replay_workflow(history, decisions=decisions, review_bundles=[bundle])
    assert final["state"]["stage"] == "complete"
    assert final["runtime_status"] == "complete"
    assert final == replay_workflow(history, decisions=decisions, review_bundles=[bundle])


def test_gate_cannot_be_skipped_or_use_missing_decision() -> None:
    history = _start()
    _children(history, "intake")
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem_analysis"])
    skipped = copy.deepcopy(history)
    _append(skipped, "stage_completed", "model_design", artifact_ids=["art_model_plan"])
    with pytest.raises(ValueError, match="stage|gate"):
        replay_workflow(skipped)

    _append(
        history,
        "gate_decided",
        "intake",
        gate="gate_1_problem",
        decision_id="dec_missing",
        outcome="approved",
        artifact_ids=["art_problem_analysis"],
    )
    with pytest.raises(ValueError, match="decision"):
        replay_workflow(history)


def test_failure_resume_and_rejection_preserve_artifacts() -> None:
    history = _start()
    _children(history, "intake")
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem_analysis"])
    rejected = _decision(
        "gate_1_problem", "dec_problem_rejected", ["art_problem_analysis"], "rejected"
    )
    _append(
        history,
        "gate_decided",
        "intake",
        gate="gate_1_problem",
        decision_id="dec_problem_rejected",
        outcome="rejected",
        artifact_ids=["art_problem_analysis"],
    )
    snapshot = replay_workflow(history, decisions=[rejected])
    assert snapshot["runtime_status"] == "blocked"
    assert snapshot["state"]["gates"]["gate_1_problem"] == "rejected"
    assert set(snapshot["state"]["latest_artifact_ids"]) == {
        "art_problem_analysis",
        "art_problem_child",
        "art_data_child",
    }

    _append(history, "resumed", "intake")
    _append(
        history,
        "stage_failed",
        "intake",
        failure_code="problem_reader_failed",
        resume_when=["restore the problem statement"],
    )
    snapshot = replay_workflow(history, decisions=[rejected])
    assert snapshot["runtime_status"] == "blocked"
    assert snapshot["resume_when"] == ["restore the problem statement"]
    assert set(snapshot["state"]["latest_artifact_ids"]) == {
        "art_problem_analysis",
        "art_problem_child",
        "art_data_child",
    }

    invalid = copy.deepcopy(history)
    _append(invalid, "stage_completed", "intake", artifact_ids=["art_new_problem"])
    with pytest.raises(ValueError, match="resume|blocked"):
        replay_workflow(invalid, decisions=[rejected])

    _append(history, "resumed", "intake")
    resumed = replay_workflow(history, decisions=[rejected])
    assert resumed["runtime_status"] == "running"
    assert set(resumed["state"]["latest_artifact_ids"]) == {
        "art_problem_analysis",
        "art_problem_child",
        "art_data_child",
    }


def test_gate4_requires_ready_current_attachment_and_revision_invalidates_it() -> None:
    # Use the complete-flow prefix up to review with helper artifacts and decisions.
    history = _start()
    decisions = [_decision("gate_1_problem", "dec_problem_approval", ["art_problem_analysis"])]
    _children(history, "intake")
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem_analysis"])
    _append(history, "gate_decided", "intake", gate="gate_1_problem", decision_id="dec_problem_approval", outcome="approved", artifact_ids=["art_problem_analysis"])
    _children(history, "model_design")
    _append(history, "stage_completed", "model_design", artifact_ids=["art_model_plan"])
    decisions.append(_decision("gate_2_model", "dec_model_approval", ["art_model_plan"]))
    _append(history, "gate_decided", "model_design", gate="gate_2_model", decision_id="dec_model_approval", outcome="approved", artifact_ids=["art_model_plan"])
    _append(history, "literature_branch_decided", "solve", literature_required=False)
    _children(history, "solve")
    _append(history, "stage_completed", "solve", artifact_ids=["art_results"])
    _append(history, "stage_completed", "outline", artifact_ids=["art_outline"])
    decisions.append(_decision("gate_3_outline", "dec_outline_approval", ["art_outline"]))
    _append(history, "gate_decided", "outline", gate="gate_3_outline", decision_id="dec_outline_approval", outcome="approved", artifact_ids=["art_outline"])
    _append(history, "stage_completed", "write", artifact_ids=["art_final_paper"])
    decisions.append(_decision("gate_4_submission", "dec_submission_approval", ["art_final_paper"]))

    missing = copy.deepcopy(history)
    _append(missing, "gate_decided", "review", gate="gate_4_submission", decision_id="dec_submission_approval", outcome="approved", artifact_ids=["art_final_paper"])
    with pytest.raises(ValueError, match="bundle"):
        replay_workflow(missing, decisions=decisions)

    bundle = _ready_bundle()
    not_ready = dict(bundle, readiness="not_ready")
    not_ready_identity = {
        key: not_ready[key]
        for key in (
            "report_ids",
            "report_digests",
            "reviewed_artifact_ids",
            "readiness",
            "open_blocking_findings",
            "errors",
        )
    }
    not_ready["bundle_id"] = f"review_bundle_{canonical_digest(not_ready_identity)[:16]}"
    bad_attach = copy.deepcopy(history)
    _children(bad_attach, "review")
    _append(bad_attach, "review_bundle_attached", "review", review_bundle_id=not_ready["bundle_id"], artifact_ids=["art_final_paper"])
    with pytest.raises(ValueError, match="ready"):
        replay_workflow(bad_attach, decisions=decisions, review_bundles=[not_ready])

    _children(history, "review")
    _append(history, "review_bundle_attached", "review", review_bundle_id=bundle["bundle_id"], artifact_ids=["art_final_paper"])
    _append(history, "stage_completed", "review", artifact_ids=["art_revised_paper"])
    stale = replay_workflow(history, decisions=decisions, review_bundles=[bundle])
    assert stale["review_bundle_id"] is None
    _append(history, "gate_decided", "review", gate="gate_4_submission", decision_id="dec_submission_approval", outcome="approved", artifact_ids=["art_final_paper"])
    with pytest.raises(ValueError, match="bundle"):
        replay_workflow(history, decisions=decisions, review_bundles=[bundle])


def test_review_failure_after_bundle_attachment_can_resume_without_deadlock() -> None:
    history = _start()
    decisions = [_decision("gate_1_problem", "dec_problem_approval", ["art_problem_analysis"])]
    _children(history, "intake")
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem_analysis"])
    _append(history, "gate_decided", "intake", gate="gate_1_problem", decision_id="dec_problem_approval", outcome="approved", artifact_ids=["art_problem_analysis"])
    _children(history, "model_design")
    _append(history, "stage_completed", "model_design", artifact_ids=["art_model_plan"])
    decisions.append(_decision("gate_2_model", "dec_model_approval", ["art_model_plan"]))
    _append(history, "gate_decided", "model_design", gate="gate_2_model", decision_id="dec_model_approval", outcome="approved", artifact_ids=["art_model_plan"])
    _append(history, "literature_branch_decided", "solve", literature_required=False)
    _children(history, "solve")
    _append(history, "stage_completed", "solve", artifact_ids=["art_results"])
    _append(history, "stage_completed", "outline", artifact_ids=["art_outline"])
    decisions.append(_decision("gate_3_outline", "dec_outline_approval", ["art_outline"]))
    _append(history, "gate_decided", "outline", gate="gate_3_outline", decision_id="dec_outline_approval", outcome="approved", artifact_ids=["art_outline"])
    _append(history, "stage_completed", "write", artifact_ids=["art_final_paper"])
    _children(history, "review")
    bundle = _ready_bundle()
    _append(history, "review_bundle_attached", "review", review_bundle_id=bundle["bundle_id"], artifact_ids=["art_final_paper"])
    _append(history, "stage_failed", "review", failure_code="bundle_publish_failed", resume_when=["rebuild all review reports"])
    _append(history, "resumed", "review")

    snapshot = replay_workflow(history, decisions=decisions, review_bundles=[bundle])
    config = load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )
    action = next_action(snapshot, config)
    assert snapshot["review_bundle_id"] is None
    assert snapshot["completed_skills"] == []
    assert action == {
        "action_type": "child_skill",
        "skill": "submission-auditor",
        "stage": "review",
    }
