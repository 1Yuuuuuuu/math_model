from __future__ import annotations

from pathlib import Path

from scripts.migrate_decision_v1_to_v2 import migrate_decision
from scripts.validate_contracts import load_json, make_validator


ROOT = Path(__file__).resolve().parents[3]


def test_dsh_shared_contract_accepts_migrated_decision() -> None:
    validator = make_validator(load_json(ROOT / "shared/contracts/decision.schema.json"))
    legacy = load_json(ROOT / "shared/fixtures/contracts/valid/decision-v1.json")
    migrated = migrate_decision(legacy, outcome="rejected")
    assert migrated["schema_version"] == "2.0"
    assert migrated["outcome"] == "rejected"
    assert list(validator.iter_errors(migrated)) == []
