from cumcm_toolkit.workflow.actions import next_action
from cumcm_toolkit.workflow.events import create_event
from cumcm_toolkit.workflow.state import replay_workflow


def _append(history: list[dict[str, object]], event_type: str, **kwargs: object) -> None:
    history.append(
        create_event(
            workspace_id="ws_resume_e2e",
            event_type=event_type,
            stage="intake",
            occurred_at=f"2026-09-10T08:{len(history):02d}:00+08:00",
            history=history,
            **kwargs,
        )
    )


def test_failure_requires_recovery_and_preserves_completed_work() -> None:
    history: list[dict[str, object]] = []
    _append(history, "workspace_started")
    _append(history, "child_completed", skill="problem-reader", artifact_ids=["art_problem"])
    _append(history, "stage_failed", failure_code="data_reader_failed", resume_when=["restore data access"])
    blocked = replay_workflow(history)
    action = next_action(
        blocked,
        {"stage_order": ["intake"], "routes": {"intake": ["problem-reader", "data-auditor"]}},
    )
    assert action["action_type"] == "recovery"
    assert blocked["state"]["latest_artifact_ids"] == ["art_problem"]

    _append(history, "resumed")
    resumed = replay_workflow(history)
    assert resumed["runtime_status"] == "running"
    assert resumed["completed_skills"] == ["problem-reader"]
    assert next_action(
        resumed,
        {"stage_order": ["intake"], "routes": {"intake": ["problem-reader", "data-auditor"]}},
    )["skill"] == "data-auditor"
