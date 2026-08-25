from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from scripts.validate_contracts import load_json, make_validator


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = make_validator(load_json(ROOT / "shared/contracts/decision.schema.json"))


def migrate_decision(
    value: Mapping[str, object], *, outcome: str
) -> dict[str, object]:
    decision = json.loads(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    )
    if decision.get("schema_version") != "1.0":
        raise ValueError("migration input must be a decision schema_version 1.0 object")
    if outcome not in {"approved", "rejected"}:
        raise ValueError("outcome must be explicitly supplied as approved or rejected")
    errors = sorted(VALIDATOR.iter_errors(decision), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"invalid version 1 decision: {errors[0].message}")
    migrated = {**decision, "schema_version": "2.0", "outcome": outcome}
    errors = sorted(VALIDATOR.iter_errors(migrated), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"migration produced invalid version 2 decision: {errors[0].message}")
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a decision 1.0 JSON file to 2.0.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--outcome", required=True, choices=("approved", "rejected"))
    args = parser.parse_args()
    source = load_json(args.input)
    migrated = migrate_decision(source, outcome=args.outcome)
    args.output.write_text(
        json.dumps(migrated, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
