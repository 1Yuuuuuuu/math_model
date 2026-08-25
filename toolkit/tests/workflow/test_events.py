from __future__ import annotations

import copy
import math

import pytest

from cumcm_toolkit.review.engine import canonical_digest
from cumcm_toolkit.workflow.events import create_event, validate_event_chain


def _start() -> dict[str, object]:
    return create_event(
        workspace_id="ws_competition_2026",
        event_type="workspace_started",
        stage="intake",
        occurred_at="2026-09-10T08:00:00+08:00",
    )


def test_create_event_is_deterministic_and_chains_previous_digest() -> None:
    first = _start()
    assert first == _start()
    assert first["sequence"] == 0
    assert first["previous_event_digest"] is None
    assert first["event_id"].startswith("evt_")

    second = create_event(
        workspace_id="ws_competition_2026",
        event_type="stage_completed",
        stage="intake",
        artifact_ids=["art_problem_analysis"],
        occurred_at="2026-09-10T09:00:00+08:00",
        history=[first],
    )
    assert second["sequence"] == 1
    assert second["previous_event_digest"] == canonical_digest(first)
    assert validate_event_chain([first, second]) == [first, second]


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"event_type": "stage_completed", "stage": "intake"}, "artifact"),
        ({"event_type": "stage_failed", "stage": "solve"}, "failure"),
        ({"event_type": "gate_decided", "stage": "intake", "gate": "gate_1_problem", "artifact_ids": ["art_problem"]}, "decision"),
        ({"event_type": "literature_branch_decided", "stage": "intake", "literature_required": True}, "stage"),
        ({"event_type": "review_bundle_attached", "stage": "review", "artifact_ids": ["art_final_paper"]}, "review_bundle"),
        ({"event_type": "submission_completed", "stage": "submission"}, "artifact"),
    ],
)
def test_event_type_fields_fail_closed(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        create_event(
            workspace_id="ws_competition_2026",
            occurred_at="2026-09-10T09:00:00+08:00",
            **kwargs,
        )


def test_chain_rejects_reorder_tamper_wrong_id_and_nonfinite() -> None:
    first = _start()
    second = create_event(
        workspace_id="ws_competition_2026",
        event_type="stage_completed",
        stage="intake",
        artifact_ids=["art_problem_analysis"],
        occurred_at="2026-09-10T09:00:00+08:00",
        history=[first],
    )
    with pytest.raises(ValueError, match="sequence|first event"):
        validate_event_chain([second, first])
    tampered = copy.deepcopy(second)
    tampered["artifact_ids"] = ["art_changed"]
    with pytest.raises(ValueError, match="event_id"):
        validate_event_chain([first, tampered])
    bad_id = copy.deepcopy(second)
    bad_id["event_id"] += "\n"
    with pytest.raises(ValueError, match="contract"):
        validate_event_chain([first, bad_id])
    nonfinite = copy.deepcopy(second)
    nonfinite["sequence"] = math.nan
    with pytest.raises(ValueError):
        validate_event_chain([first, nonfinite])


def test_chain_rejects_an_event_timestamp_earlier_than_its_predecessor() -> None:
    first = create_event(
        workspace_id="ws_competition_2026",
        event_type="workspace_started",
        stage="intake",
        occurred_at="2026-09-10T10:00:00+08:00",
    )
    second = create_event(
        workspace_id="ws_competition_2026",
        event_type="child_completed",
        stage="intake",
        skill="problem-reader",
        artifact_ids=["art_problem"],
        occurred_at="2026-09-10T09:59:59+08:00",
        history=[first],
    )
    with pytest.raises(ValueError, match="timestamp"):
        validate_event_chain([first, second])


def test_exact_duplicate_delivery_is_idempotent_but_conflict_rejects() -> None:
    first = _start()
    assert validate_event_chain([first, copy.deepcopy(first)]) == [first]
    conflict = copy.deepcopy(first)
    conflict["stage"] = "model_design"
    with pytest.raises(ValueError, match="duplicate event_id"):
        validate_event_chain([first, conflict])
