from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import ValidationError

from scripts.validate_contracts import load_json, make_validator


def test_workflow_event_contract_is_registered_and_strict(project_root: Path) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    entries = {entry["id"]: entry for entry in catalog["contracts"]}
    assert len(entries) == 16
    assert "workflow-event" in entries
    entry = entries["workflow-event"]
    schema = load_json(project_root / entry["schema"])
    validator = make_validator(schema)
    for relative in entry["valid_examples"]:
        validator.validate(load_json(project_root / relative))
    for relative in entry["invalid_examples"]:
        with pytest.raises(ValidationError):
            validator.validate(load_json(project_root / relative))


def test_gate_event_without_decision_fails_once(project_root: Path) -> None:
    schema = load_json(project_root / "shared/contracts/workflow-event.schema.json")
    fixture = load_json(
        project_root
        / "shared/fixtures/contracts/invalid/workflow-event-gate-without-decision.json"
    )
    errors = list(make_validator(schema).iter_errors(fixture))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == ("decision_id",)
    assert errors[0].validator == "type"
