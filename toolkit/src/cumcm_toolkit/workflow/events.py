from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from cumcm_toolkit.review.engine import canonical_digest
from scripts.validate_contracts import load_json, make_validator


_ROOT = Path(__file__).resolve().parents[4]
_SCHEMA = load_json(_ROOT / "shared/contracts/workflow-event.schema.json")
_VALIDATOR = make_validator(_SCHEMA)


def _material(event: Mapping[str, object]) -> dict[str, object]:
    return {key: copy.deepcopy(value) for key, value in event.items() if key != "event_id"}


def _expected_id(event: Mapping[str, object]) -> str:
    return f"evt_{canonical_digest(_material(event))[:16]}"


def _validate_contract(event: Mapping[str, object]) -> dict[str, object]:
    try:
        copied = json.loads(
            json.dumps(
                dict(event),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"workflow event must be canonical JSON: {exc}") from exc
    errors = sorted(_VALIDATOR.iter_errors(copied), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "event"
        raise ValueError(f"workflow event contract failed at {location}: {errors[0].message}")
    return copied


def validate_event_chain(
    events: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    unique: list[dict[str, object]] = []
    seen: dict[str, dict[str, object]] = {}
    for value in events:
        if not isinstance(value, Mapping):
            raise ValueError("workflow event must be a mapping")
        raw = copy.deepcopy(dict(value))
        event_id = raw.get("event_id")
        if isinstance(event_id, str) and event_id in seen:
            if raw == seen[event_id]:
                continue
            raise ValueError(f"duplicate event_id has conflicting content: {event_id}")
        event = _validate_contract(raw)
        event_id = str(event["event_id"])
        seen[event_id] = event
        unique.append(event)
    if not unique:
        return []
    workspace_id = unique[0]["workspace_id"]
    previous: dict[str, object] | None = None
    for index, event in enumerate(unique):
        if event["sequence"] != index:
            raise ValueError(f"event sequence must be contiguous at index {index}")
        if event["workspace_id"] != workspace_id:
            raise ValueError("all events must belong to one workspace")
        if index == 0:
            if event["event_type"] != "workspace_started":
                raise ValueError("first event must be workspace_started")
            if event["previous_event_digest"] is not None:
                raise ValueError("first event cannot have a previous digest")
        else:
            assert previous is not None
            if event["previous_event_digest"] != canonical_digest(previous):
                raise ValueError(f"previous event digest mismatch at sequence {index}")
            previous_time = datetime.fromisoformat(
                str(previous["occurred_at"]).replace("Z", "+00:00")
            )
            event_time = datetime.fromisoformat(
                str(event["occurred_at"]).replace("Z", "+00:00")
            )
            if event_time < previous_time:
                raise ValueError(f"event timestamp moves backward at sequence {index}")
        if event["event_id"] != _expected_id(event):
            raise ValueError(f"event_id does not match canonical event material at sequence {index}")
        previous = event
    return unique


def create_event(
    *,
    workspace_id: str,
    event_type: str,
    stage: str,
    occurred_at: str,
    history: Iterable[Mapping[str, object]] = (),
    skill: str | None = None,
    gate: str | None = None,
    decision_id: str | None = None,
    outcome: str | None = None,
    artifact_ids: Iterable[str] = (),
    review_bundle_id: str | None = None,
    literature_required: bool | None = None,
    failure_code: str | None = None,
    resume_when: Iterable[str] = (),
) -> dict[str, object]:
    checked_history = validate_event_chain(history)
    if checked_history and checked_history[0]["workspace_id"] != workspace_id:
        raise ValueError("new event workspace_id must match history")
    sequence = len(checked_history)
    event: dict[str, Any] = {
        "schema_version": "1.0",
        "workspace_id": workspace_id,
        "sequence": sequence,
        "previous_event_digest": (
            canonical_digest(checked_history[-1]) if checked_history else None
        ),
        "event_type": event_type,
        "stage": stage,
        "skill": skill,
        "gate": gate,
        "decision_id": decision_id,
        "outcome": outcome,
        "artifact_ids": list(artifact_ids),
        "review_bundle_id": review_bundle_id,
        "literature_required": literature_required,
        "failure_code": failure_code,
        "resume_when": list(resume_when),
        "occurred_at": occurred_at,
    }
    event["event_id"] = _expected_id(event)
    return _validate_contract(event)
