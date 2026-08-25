from __future__ import annotations

from pathlib import Path

from cumcm_toolkit.workflow.actions import next_action
from cumcm_toolkit.workflow.config import load_workflow_config


ROOT = Path(__file__).resolve().parents[3]


def _config() -> dict:
    return load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )


def _snapshot(stage: str, **changes: object) -> dict[str, object]:
    value = {
        "state": {"stage": stage, "gates": {}, "latest_artifact_ids": []},
        "runtime_status": "running",
        "blocked_reason": None,
        "resume_when": [],
        "waiting_gate": None,
        "literature_branch": "undecided",
        "review_bundle_id": None,
        "completed_skills": [],
    }
    value.update(changes)
    return value


def test_routes_one_child_skill_at_a_time_then_finalizes_stage() -> None:
    config = _config()
    assert next_action(_snapshot("intake"), config) == {
        "action_type": "child_skill",
        "skill": "problem-reader",
        "stage": "intake",
    }
    assert next_action(_snapshot("intake", completed_skills=["problem-reader"]), config)[
        "skill"
    ] == "data-auditor"
    assert next_action(
        _snapshot("intake", completed_skills=["problem-reader", "data-auditor"]),
        config,
    )["action_type"] == "finalize_stage"


def test_human_and_recovery_states_stop_automatic_execution() -> None:
    config = _config()
    gate = next_action(
        _snapshot(
            "intake", runtime_status="waiting_human", waiting_gate="gate_1_problem"
        ),
        config,
    )
    assert gate == {
        "action_type": "human_gate",
        "gate": "gate_1_problem",
        "stage": "intake",
    }
    recovery = next_action(
        _snapshot(
            "solve",
            runtime_status="blocked",
            blocked_reason="solver_failed",
            resume_when=["restore solver"],
        ),
        config,
    )
    assert recovery["action_type"] == "recovery"
    assert recovery["resume_when"] == ["restore solver"]


def test_literature_branch_is_optional_and_has_no_human_gate() -> None:
    config = _config()
    completed = ["solver", "sensitivity-analyst"]
    decision = next_action(_snapshot("solve", completed_skills=completed), config)
    assert decision["action_type"] == "decide_literature_branch"
    required = next_action(
        _snapshot(
            "solve", completed_skills=completed, literature_branch="required"
        ),
        config,
    )
    assert required == {
        "action_type": "child_skill",
        "skill": "literature-researcher",
        "stage": "solve",
    }
    finalized = next_action(
        _snapshot(
            "solve",
            completed_skills=completed + ["literature-researcher"],
            literature_branch="required",
        ),
        config,
    )
    assert finalized["action_type"] == "finalize_stage"
    skipped = next_action(
        _snapshot("solve", completed_skills=completed, literature_branch="skipped"),
        config,
    )
    assert skipped["action_type"] == "finalize_stage"


def test_paper_review_bundle_submission_and_complete_actions() -> None:
    config = _config()
    assert next_action(_snapshot("outline"), config) == {
        "action_type": "stage_work",
        "capability": "paper_outline",
        "stage": "outline",
    }
    assert next_action(_snapshot("write"), config)["capability"] == "paper_write"
    review_skills = config["review"]["skills"]
    first = next_action(_snapshot("review"), config)
    assert first["skill"] == review_skills[0]
    bundle = next_action(
        _snapshot("review", completed_skills=list(review_skills)), config
    )
    assert bundle["action_type"] == "build_review_bundle"
    assert next_action(_snapshot("submission"), config)["action_type"] == "package_submission"
    assert next_action(_snapshot("complete", runtime_status="complete"), config) == {
        "action_type": "complete",
        "stage": "complete",
    }
