from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cumcm_toolkit.workflow.events import create_event
from cumcm_toolkit.workflow.persistence import (
    load_workflow_checkpoint,
    replay_workflow_checkpoint,
    save_workflow_checkpoint,
)
from cumcm_toolkit.workflow.state import replay_workflow


def _history() -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    start = datetime(2026, 9, 10, 8, tzinfo=timezone(timedelta(hours=8)))
    for offset, (event_type, skill, artifact_ids) in enumerate(
        (
            ("workspace_started", None, []),
            ("child_completed", "problem-reader", ["art_problem_child"]),
            ("child_completed", "data-auditor", ["art_data_child"]),
            ("stage_completed", None, ["art_problem_analysis"]),
        )
    ):
        kwargs: dict[str, object] = {"artifact_ids": artifact_ids}
        if skill is not None:
            kwargs["skill"] = skill
        history.append(
            create_event(
                workspace_id="ws_persisted_case",
                event_type=event_type,
                stage="intake",
                occurred_at=(start + timedelta(minutes=offset)).isoformat(),
                history=history,
                **kwargs,
            )
        )
    return history


def test_restart_loads_checkpoint_from_disk_and_replays_identically(tmp_path: Path) -> None:
    path = tmp_path / "workflow-checkpoint.json"
    history = _history()
    save_workflow_checkpoint(path, events=history, decisions=[], review_bundles=[])

    reloaded = load_workflow_checkpoint(path)
    after_restart = replay_workflow_checkpoint(path)

    assert reloaded["events"] == history
    assert after_restart == replay_workflow(history)
    assert after_restart["runtime_status"] == "waiting_human"


def test_checkpoint_detects_disk_tampering(tmp_path: Path) -> None:
    path = tmp_path / "workflow-checkpoint.json"
    save_workflow_checkpoint(path, events=_history(), decisions=[], review_bundles=[])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["events"][0]["workspace_id"] = "ws_tampered_case"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        load_workflow_checkpoint(path)
