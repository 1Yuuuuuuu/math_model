from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.migrate_decision_v1_to_v2 import migrate_decision
from scripts.validate_contracts import load_json, make_validator


def test_decision_v1_and_v2_validate_and_migration_is_deterministic(
    project_root: Path,
) -> None:
    validator = make_validator(
        load_json(project_root / "shared/contracts/decision.schema.json")
    )
    legacy = load_json(project_root / "shared/fixtures/contracts/valid/decision-v1.json")
    current = load_json(project_root / "shared/fixtures/contracts/valid/decision.json")
    assert list(validator.iter_errors(legacy)) == []
    assert list(validator.iter_errors(current)) == []

    first = migrate_decision(legacy, outcome="approved")
    second = migrate_decision(legacy, outcome="approved")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schema_version"] == "2.0"
    assert first["outcome"] == "approved"
    assert list(validator.iter_errors(first)) == []


def test_decision_migration_never_infers_outcome(project_root: Path) -> None:
    legacy = load_json(project_root / "shared/fixtures/contracts/valid/decision-v1.json")
    with pytest.raises(ValueError, match="explicitly supplied"):
        migrate_decision(legacy, outcome="maybe")
