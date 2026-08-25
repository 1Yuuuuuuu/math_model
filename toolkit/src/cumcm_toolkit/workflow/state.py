from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from pathlib import Path

from cumcm_toolkit.review.engine import canonical_digest
from cumcm_toolkit.workflow.events import validate_event_chain
from cumcm_toolkit.workflow.config import load_workflow_config
from cumcm_toolkit.workflow.gates import (
    GATE_STAGES,
    index_decisions,
    index_review_bundles,
    validate_gate_decision,
)
from scripts.validate_contracts import load_json, make_validator


_ROOT = Path(__file__).resolve().parents[4]
_STATE_VALIDATOR = make_validator(
    load_json(_ROOT / "shared/contracts/workflow-state.schema.json")
)
_STAGE_GATES = {stage: gate for gate, (stage, _) in GATE_STAGES.items()}
_WORKFLOW_CONFIG = load_workflow_config(
    _ROOT / "shared/workflows/stage-transitions.yaml",
    _ROOT / "shared/workflows/cumcm-72h.yaml",
    skill_catalog_path=_ROOT / "adapters/codex/skills/catalog.json",
)
_REQUIRED_STAGE_SKILLS = {
    stage: tuple(skills) for stage, skills in _WORKFLOW_CONFIG["routes"].items()
}
_LITERATURE_SKILL = str(_WORKFLOW_CONFIG["literature_branch"]["skill"])


def _validate_state(state: dict[str, object]) -> None:
    errors = sorted(_STATE_VALIDATOR.iter_errors(state), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "state"
        raise ValueError(f"derived workflow state violates contract at {location}: {errors[0].message}")


def replay_workflow(
    events: Iterable[Mapping[str, object]],
    *,
    decisions: Iterable[Mapping[str, object]] = (),
    review_bundles: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    history = validate_event_chain(events)
    if not history:
        raise ValueError("workflow history must contain workspace_started")
    decision_index = index_decisions(decisions)
    bundle_index = index_review_bundles(review_bundles)
    first = history[0]
    state: dict[str, object] = {
        "schema_version": "1.0",
        "workspace_id": first["workspace_id"],
        "stage": "intake",
        "gates": {
            "gate_1_problem": "pending",
            "gate_2_model": "pending",
            "gate_3_outline": "pending",
            "gate_4_submission": "pending",
        },
        "latest_artifact_ids": [],
        "updated_at": first["occurred_at"],
    }
    runtime_status = "running"
    blocked_reason: str | None = None
    resume_when: list[str] = []
    waiting_gate: str | None = None
    stage_ready_for_gate = False
    literature_branch = "undecided"
    attached_bundle_id: str | None = None
    attached_bundle_digest: str | None = None
    completed_skills: list[str] = []
    child_artifact_ids: set[str] = set()
    literature_artifact_ids: set[str] = set()

    for event in history[1:]:
        event_type = str(event["event_type"])
        stage = str(state["stage"])
        if event["stage"] != stage:
            raise ValueError(
                f"event stage {event['stage']} does not match current stage {stage}; a gate may have been skipped"
            )
        if runtime_status == "blocked" and event_type != "resumed":
            raise ValueError("workflow is blocked and requires a resumed event")

        artifacts = set(state["latest_artifact_ids"])
        if event_type == "workspace_started":
            raise ValueError("workspace_started may appear only once")
        if event_type == "stage_failed":
            runtime_status = "blocked"
            blocked_reason = str(event["failure_code"])
            resume_when = list(event["resume_when"])
            waiting_gate = None
            stage_ready_for_gate = False
            if stage == "review" and attached_bundle_id is not None:
                attached_bundle_id = None
                attached_bundle_digest = None
                completed_skills = []
                child_artifact_ids = set()
        elif event_type == "resumed":
            if runtime_status != "blocked":
                raise ValueError("resumed event requires a blocked workflow")
            runtime_status = "running"
            blocked_reason = None
            resume_when = []
            waiting_gate = None
            stage_ready_for_gate = False
            current_gate = _STAGE_GATES.get(stage)
            if current_gate is not None and state["gates"][current_gate] == "rejected":
                state["gates"][current_gate] = "pending"
        elif event_type == "literature_branch_decided":
            if literature_branch != "undecided":
                raise ValueError("literature branch has already been decided")
            literature_branch = "required" if event["literature_required"] else "skipped"
        elif event_type == "child_completed":
            skill = str(event["skill"])
            if skill in completed_skills:
                raise ValueError(f"child Skill already completed in this stage: {skill}")
            expected = list(_REQUIRED_STAGE_SKILLS[stage])
            if stage == "solve" and literature_branch == "required":
                expected.append(_LITERATURE_SKILL)
            position = len(completed_skills)
            if position >= len(expected):
                raise ValueError(f"no child Skill is allowed at stage {stage}")
            if skill != expected[position]:
                raise ValueError(
                    f"expected child Skill {expected[position]} at stage {stage}, got {skill}"
                )
            completed_skills.append(skill)
            artifacts.update(event["artifact_ids"])
            child_artifact_ids.update(event["artifact_ids"])
            if skill == _LITERATURE_SKILL:
                literature_artifact_ids.update(event["artifact_ids"])
            state["latest_artifact_ids"] = sorted(artifacts)
            if attached_bundle_id is not None:
                attached_bundle_id = None
                attached_bundle_digest = None
        elif event_type == "stage_completed":
            event_artifacts = set(event["artifact_ids"])
            required = list(_REQUIRED_STAGE_SKILLS[stage])
            if stage in {"intake", "model_design", "solve"}:
                if completed_skills[: len(required)] != required:
                    raise ValueError(
                        f"stage {stage} cannot complete before required child Skills: {', '.join(required)}"
                    )
                if stage == "solve" and literature_branch == "required" and (
                    not completed_skills or completed_skills[-1] != _LITERATURE_SKILL
                ):
                    raise ValueError(
                        f"required literature branch must complete {_LITERATURE_SKILL}"
                    )
            artifacts.update(event_artifacts)
            state["latest_artifact_ids"] = sorted(artifacts)
            if attached_bundle_id is not None:
                attached_bundle_id = None
                attached_bundle_digest = None
            if stage in {"intake", "model_design", "outline"}:
                waiting_gate = _STAGE_GATES[stage]
                runtime_status = "waiting_human"
                stage_ready_for_gate = True
                if stage == "outline" and literature_branch == "required":
                    literature_branch = "complete"
            elif stage == "solve":
                if literature_branch == "undecided":
                    raise ValueError("solve completion requires a literature branch decision")
                state["stage"] = "outline"
                runtime_status = "running"
                completed_skills = []
                child_artifact_ids = set()
            elif stage == "write":
                state["stage"] = "review"
                runtime_status = "running"
                completed_skills = []
                child_artifact_ids = set()
            elif stage == "review":
                runtime_status = "running"
                waiting_gate = None
                stage_ready_for_gate = False
                completed_skills = []
                child_artifact_ids = set()
            else:
                raise ValueError(f"stage_completed is not valid for stage {stage}")
        elif event_type == "review_bundle_attached":
            required_reviewers = list(_REQUIRED_STAGE_SKILLS["review"])
            if completed_skills != required_reviewers:
                raise ValueError(
                    "review bundle requires all configured reviewer Skills in order"
                )
            bundle_id = str(event["review_bundle_id"])
            bundle = bundle_index.get(bundle_id)
            if bundle is None:
                raise ValueError(f"unresolved review bundle: {bundle_id}")
            if bundle["readiness"] != "ready_for_phase_6":
                raise ValueError("review bundle is not ready_for_phase_6")
            reviewed_artifacts = set(bundle["reviewed_artifact_ids"])
            if set(event["artifact_ids"]) != reviewed_artifacts:
                raise ValueError("review bundle attachment artifacts do not match the bundle")
            if not reviewed_artifacts.issubset(set(state["latest_artifact_ids"])):
                raise ValueError("review bundle refers to artifacts outside the workflow state")
            attached_bundle_id = bundle_id
            attached_bundle_digest = canonical_digest(bundle)
            waiting_gate = "gate_4_submission"
            runtime_status = "waiting_human"
            stage_ready_for_gate = True
        elif event_type == "gate_decided":
            gate = str(event["gate"])
            if gate == "gate_4_submission" and attached_bundle_id is None:
                raise ValueError("gate_4_submission requires an attached ready review bundle")
            if (
                gate == "gate_3_outline"
                and literature_branch == "complete"
                and not literature_artifact_ids.issubset(set(event["artifact_ids"]))
            ):
                raise ValueError(
                    "gate_3_outline decision must bind required literature artifacts"
                )
            if not stage_ready_for_gate or waiting_gate != gate:
                raise ValueError(f"human gate {gate} is not ready; required stage work is incomplete")
            outcome, next_stage = validate_gate_decision(
                state,
                event,
                decision_index,
                attached_bundle_id=attached_bundle_id,
                review_bundles=bundle_index,
            )
            state["gates"][gate] = outcome
            stage_ready_for_gate = False
            waiting_gate = None
            if outcome == "rejected":
                runtime_status = "blocked"
                blocked_reason = f"{gate}_rejected"
                resume_when = ["revise the gate artifacts and append a resumed event"]
                completed_skills = []
                child_artifact_ids = set()
            else:
                state["stage"] = next_stage
                runtime_status = "running"
                completed_skills = []
                child_artifact_ids = set()
        elif event_type == "submission_completed":
            if state["gates"]["gate_4_submission"] != "approved":
                raise ValueError("submission cannot complete before gate_4_submission approval")
            artifacts.update(event["artifact_ids"])
            state["latest_artifact_ids"] = sorted(artifacts)
            state["stage"] = "complete"
            runtime_status = "complete"
            completed_skills = []
            child_artifact_ids = set()
        else:
            raise ValueError(f"unsupported workflow event: {event_type}")
        state["updated_at"] = event["occurred_at"]
        _validate_state(state)

    _validate_state(state)
    return {
        "state": copy.deepcopy(state),
        "runtime_status": runtime_status,
        "blocked_reason": blocked_reason,
        "resume_when": resume_when,
        "waiting_gate": waiting_gate,
        "literature_branch": literature_branch,
        "review_bundle_id": attached_bundle_id,
        "review_bundle_digest": attached_bundle_digest,
        "completed_skills": list(completed_skills),
        "last_event_digest": canonical_digest(history[-1]),
    }
