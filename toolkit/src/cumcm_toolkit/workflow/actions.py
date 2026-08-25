from __future__ import annotations

from collections.abc import Mapping


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def next_action(
    snapshot: Mapping[str, object], config: Mapping[str, object]
) -> dict[str, object]:
    """Return exactly one deterministic next action for a replayed workflow."""
    state = snapshot.get("state")
    if not isinstance(state, Mapping):
        raise ValueError("snapshot.state must be an object")
    stage = _require_string(state.get("stage"), "snapshot.state.stage")
    stage_order = config.get("stage_order")
    routes = config.get("routes")
    if not isinstance(stage_order, list) or stage not in stage_order:
        raise ValueError(f"unknown workflow stage: {stage}")
    if not isinstance(routes, Mapping):
        raise ValueError("config.routes must be an object")

    runtime_status = _require_string(
        snapshot.get("runtime_status"), "snapshot.runtime_status"
    )
    if runtime_status == "complete":
        if stage != "complete":
            raise ValueError("complete runtime status requires the complete stage")
        return {"action_type": "complete", "stage": stage}
    if runtime_status == "blocked":
        resume_when = snapshot.get("resume_when")
        if not isinstance(resume_when, list) or not all(
            isinstance(item, str) and item for item in resume_when
        ):
            raise ValueError("blocked workflow requires resume_when instructions")
        return {
            "action_type": "recovery",
            "reason": _require_string(
                snapshot.get("blocked_reason"), "snapshot.blocked_reason"
            ),
            "resume_when": list(resume_when),
            "stage": stage,
        }
    if runtime_status == "waiting_human":
        return {
            "action_type": "human_gate",
            "gate": _require_string(snapshot.get("waiting_gate"), "snapshot.waiting_gate"),
            "stage": stage,
        }
    if runtime_status != "running":
        raise ValueError(f"unsupported runtime status: {runtime_status}")

    completed = snapshot.get("completed_skills")
    if not isinstance(completed, list) or not all(
        isinstance(item, str) and item for item in completed
    ):
        raise ValueError("snapshot.completed_skills must be a string list")
    if len(set(completed)) != len(completed):
        raise ValueError("snapshot.completed_skills must not contain duplicates")
    stage_routes = routes.get(stage)
    if not isinstance(stage_routes, list) or not all(
        isinstance(item, str) and item for item in stage_routes
    ):
        raise ValueError(f"config.routes.{stage} must be a string list")
    for skill in stage_routes:
        if skill not in completed:
            return {"action_type": "child_skill", "skill": skill, "stage": stage}

    if stage == "solve":
        branch = snapshot.get("literature_branch")
        if branch == "undecided":
            return {"action_type": "decide_literature_branch", "stage": stage}
        if branch == "required":
            literature = config.get("literature_branch")
            if not isinstance(literature, Mapping):
                raise ValueError("config.literature_branch must be an object")
            skill = _require_string(literature.get("skill"), "literature_branch.skill")
            if skill not in completed:
                return {"action_type": "child_skill", "skill": skill, "stage": stage}
        elif branch not in {"skipped", "complete"}:
            raise ValueError(f"unsupported literature branch: {branch}")
        return {"action_type": "finalize_stage", "stage": stage}
    if stage in {"intake", "model_design"}:
        return {"action_type": "finalize_stage", "stage": stage}
    if stage == "outline":
        return {
            "action_type": "stage_work",
            "capability": "paper_outline",
            "stage": stage,
        }
    if stage == "write":
        return {
            "action_type": "stage_work",
            "capability": "paper_write",
            "stage": stage,
        }
    if stage == "review":
        if snapshot.get("review_bundle_id") is not None:
            raise ValueError("attached review bundle must transition to a human gate")
        return {"action_type": "build_review_bundle", "stage": stage}
    if stage == "submission":
        return {"action_type": "package_submission", "stage": stage}
    if stage == "complete":
        raise ValueError("complete stage requires complete runtime status")
    raise ValueError(f"no next action is defined for stage: {stage}")
