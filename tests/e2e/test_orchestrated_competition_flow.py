import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cumcm_toolkit.workflow.actions import next_action
from cumcm_toolkit.workflow.config import load_workflow_config
from cumcm_toolkit.workflow.events import create_event
from cumcm_toolkit.workflow.state import replay_workflow


ROOT = Path(__file__).resolve().parents[2]


def _append(history: list[dict[str, object]], event_type: str, stage: str, **kwargs: object) -> None:
    occurred_at = (
        datetime(2026, 9, 10, 8, tzinfo=timezone(timedelta(hours=8)))
        + timedelta(minutes=len(history))
    ).isoformat()
    history.append(create_event(
        workspace_id="ws_orchestrated_e2e", event_type=event_type, stage=stage,
        occurred_at=occurred_at, history=history, **kwargs
    ))


def _decision(gate: str, decision_id: str, artifact: str) -> dict[str, object]:
    return {
        "schema_version": "2.0", "decision_id": decision_id, "gate": gate,
        "outcome": "approved", "selected_option": "approve", "rationale": "Human approval.",
        "artifact_ids": [artifact], "decided_by": "human", "decided_at": "2026-09-10T10:00:00+08:00",
    }


def test_replay_and_policy_reach_submission_without_bypassing_gates() -> None:
    config = load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml", ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )
    history: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    _append(history, "workspace_started", "intake")
    assert next_action(replay_workflow(history), config)["skill"] == "problem-reader"
    for skill, artifact in (("problem-reader", "art_problem"), ("data-auditor", "art_data")):
        _append(history, "child_completed", "intake", skill=skill, artifact_ids=[artifact])
    assert next_action(replay_workflow(history), config)["action_type"] == "finalize_stage"
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem"])
    decisions.append(_decision("gate_1_problem", "dec_problem", "art_problem"))
    _append(history, "gate_decided", "intake", gate="gate_1_problem", decision_id="dec_problem", outcome="approved", artifact_ids=["art_problem"])
    assert replay_workflow(history, decisions=decisions)["state"]["stage"] == "model_design"

    _append(history, "child_completed", "model_design", skill="model-selector", artifact_ids=["art_model"])
    _append(history, "stage_completed", "model_design", artifact_ids=["art_model"])
    decisions.append(_decision("gate_2_model", "dec_model", "art_model"))
    _append(history, "gate_decided", "model_design", gate="gate_2_model", decision_id="dec_model", outcome="approved", artifact_ids=["art_model"])
    _append(history, "literature_branch_decided", "solve", literature_required=False)
    _append(history, "child_completed", "solve", skill="solver", artifact_ids=["art_results"])
    _append(history, "child_completed", "solve", skill="sensitivity-analyst", artifact_ids=["art_sensitivity"])
    _append(history, "stage_completed", "solve", artifact_ids=["art_results"])
    _append(history, "stage_completed", "outline", artifact_ids=["art_outline"])
    decisions.append(_decision("gate_3_outline", "dec_outline", "art_outline"))
    _append(history, "gate_decided", "outline", gate="gate_3_outline", decision_id="dec_outline", outcome="approved", artifact_ids=["art_outline"])
    _append(history, "stage_completed", "write", artifact_ids=["art_final_paper"])

    bundle = json.loads((ROOT / "shared/fixtures/contracts/valid/review-bundle.json").read_text(encoding="utf-8"))
    for skill, artifact in (
        ("submission-auditor", "art_review_submission"),
        ("repro-reviewer", "art_review_repro"),
        ("model-reviewer", "art_review_model"),
        ("paper-reviewer", "art_review_paper"),
        ("red-team-reviewer", "art_review_red_team"),
    ):
        _append(history, "child_completed", "review", skill=skill, artifact_ids=[artifact])
    _append(history, "review_bundle_attached", "review", review_bundle_id=bundle["bundle_id"], artifact_ids=["art_final_paper"])
    decisions.append(_decision("gate_4_submission", "dec_submit", "art_final_paper"))
    _append(history, "gate_decided", "review", gate="gate_4_submission", decision_id="dec_submit", outcome="approved", artifact_ids=["art_final_paper"])
    snapshot = replay_workflow(history, decisions=decisions, review_bundles=[bundle])
    assert snapshot["state"]["stage"] == "submission"
    assert next_action(snapshot, config)["action_type"] == "package_submission"
