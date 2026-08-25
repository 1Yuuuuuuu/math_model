from __future__ import annotations

import pytest

from cumcm_toolkit.workflow.events import create_event
from cumcm_toolkit.workflow.state import replay_workflow


def _append(
    history: list[dict[str, object]], event_type: str, stage: str, **kwargs: object
) -> None:
    history.append(
        create_event(
            workspace_id="ws_policy_integrity",
            event_type=event_type,
            stage=stage,
            occurred_at=f"2026-09-10T08:{len(history):02d}:00+08:00",
            history=history,
            **kwargs,
        )
    )


def _start() -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    _append(history, "workspace_started", "intake")
    return history


def test_stage_cannot_complete_before_registered_child_skills() -> None:
    history = _start()
    _append(history, "stage_completed", "intake", artifact_ids=["art_problem"])
    with pytest.raises(ValueError, match="required child Skills"):
        replay_workflow(history)


def test_child_skill_must_follow_configured_order() -> None:
    history = _start()
    _append(
        history,
        "child_completed",
        "intake",
        skill="data-auditor",
        artifact_ids=["art_data"],
    )
    with pytest.raises(ValueError, match="expected child Skill problem-reader"):
        replay_workflow(history)


@pytest.mark.parametrize(
    ("event_type", "extra"),
    [
        ("child_completed", {"skill": "problem-reader", "artifact_ids": ["art_problem"], "gate": "gate_1_problem"}),
        ("stage_failed", {"failure_code": "failed", "resume_when": ["repair"], "artifact_ids": ["art_hidden"]}),
        ("resumed", {"outcome": "approved"}),
    ],
)
def test_event_types_reject_irrelevant_non_null_fields(
    event_type: str, extra: dict[str, object]
) -> None:
    history = _start()
    with pytest.raises(ValueError, match="contract"):
        _append(history, event_type, "intake", **extra)


def test_required_literature_cannot_be_declared_complete_without_candidates() -> None:
    history = _start()
    for skill, artifact in (
        ("problem-reader", "art_problem"),
        ("data-auditor", "art_data"),
    ):
        _append(history, "child_completed", "intake", skill=skill, artifact_ids=[artifact])
    _append(
        history,
        "stage_completed",
        "intake",
        artifact_ids=["art_problem", "art_data"],
    )
    decision = {
        "schema_version": "2.0",
        "decision_id": "dec_problem_policy",
        "gate": "gate_1_problem",
        "outcome": "approved",
        "selected_option": "approve",
        "rationale": "Human approval.",
        "artifact_ids": ["art_problem", "art_data"],
        "decided_by": "human",
        "decided_at": "2026-09-10T09:00:00+08:00",
    }
    _append(
        history,
        "gate_decided",
        "intake",
        gate="gate_1_problem",
        decision_id="dec_problem_policy",
        outcome="approved",
        artifact_ids=["art_problem", "art_data"],
    )
    _append(
        history,
        "child_completed",
        "model_design",
        skill="model-selector",
        artifact_ids=["art_model"],
    )
    _append(history, "stage_completed", "model_design", artifact_ids=["art_model"])
    model_decision = {
        **decision,
        "decision_id": "dec_model_policy",
        "gate": "gate_2_model",
        "artifact_ids": ["art_model"],
    }
    _append(
        history,
        "gate_decided",
        "model_design",
        gate="gate_2_model",
        decision_id="dec_model_policy",
        outcome="approved",
        artifact_ids=["art_model"],
    )
    _append(
        history,
        "child_completed",
        "solve",
        skill="solver",
        artifact_ids=["art_solution"],
    )
    _append(
        history,
        "child_completed",
        "solve",
        skill="sensitivity-analyst",
        artifact_ids=["art_sensitivity"],
    )
    _append(history, "literature_branch_decided", "solve", literature_required=True)
    before_invalid_completion = list(history)
    _append(
        history,
        "stage_completed",
        "solve",
        artifact_ids=["art_solution", "art_sensitivity"],
    )
    with pytest.raises(ValueError, match="literature-researcher"):
        replay_workflow(history, decisions=[decision, model_decision])

    history = before_invalid_completion
    _append(
        history,
        "child_completed",
        "solve",
        skill="literature-researcher",
        artifact_ids=["art_literature_candidates"],
    )
    _append(history, "stage_completed", "solve", artifact_ids=["art_solution"])
    _append(history, "stage_completed", "outline", artifact_ids=["art_outline"])
    outline_decision = {
        **decision,
        "decision_id": "dec_outline_policy",
        "gate": "gate_3_outline",
        "artifact_ids": ["art_outline"],
    }
    _append(
        history,
        "gate_decided",
        "outline",
        gate="gate_3_outline",
        decision_id="dec_outline_policy",
        outcome="approved",
        artifact_ids=["art_outline"],
    )
    with pytest.raises(ValueError, match="literature artifacts"):
        replay_workflow(
            history, decisions=[decision, model_decision, outline_decision]
        )
