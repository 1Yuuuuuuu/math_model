from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "experiment.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def strict_loads(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_nonstandard_json_constant)


def _validate_finite(value: object, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number in {where}: {value}")
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_finite(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_finite(item, f"{where}[{index}]")


def _stable_parameters(parameters: dict[str, Any]) -> str:
    return json.dumps(
        parameters,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def derive_experiment_id(
    input_artifact_ids: list[str],
    code_artifact_id: str,
    parameters: dict[str, Any],
    random_seed: int | None,
) -> str:
    material = "\n".join(
        [
            "|".join(sorted(input_artifact_ids)),
            code_artifact_id,
            _stable_parameters(parameters),
            "none" if random_seed is None else str(random_seed),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"exp_{digest[:24]}"


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lock_sha256_for(project_root: Path) -> str:
    lock = project_root / "uv.lock"
    if not lock.is_file():
        raise FileNotFoundError(f"uv.lock not found: {lock}")
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def create_experiment_record(
    *,
    input_artifact_ids: list[str],
    code_artifact_id: str,
    parameters: dict[str, Any],
    random_seed: int | None,
    status: str,
    output_artifact_ids: list[str],
    metrics: dict[str, float],
    project_root: Path,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be a JSON object")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a JSON object")
    parameters = dict(parameters)
    metrics = dict(metrics)
    _validate_finite(parameters, "parameters")
    _validate_finite(metrics, "metrics")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if python_version != "3.11":
        raise ValueError(f"requires Python 3.11, running {python_version}")
    now = utc_now_rfc3339()
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": derive_experiment_id(
            input_artifact_ids, code_artifact_id, parameters, random_seed
        ),
        "input_artifact_ids": list(input_artifact_ids),
        "code_artifact_id": code_artifact_id,
        "parameters": parameters,
        "random_seed": random_seed,
        "environment": {
            "python_version": python_version,
            "lock_sha256": lock_sha256_for(project_root),
        },
        "started_at": started_at or now,
        "finished_at": finished_at or now,
        "status": status,
        "output_artifact_ids": list(output_artifact_ids),
        "metrics": metrics,
    }
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"experiment record invalid: {errors[0].message}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an experiment manifest record")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--input-artifacts", required=True, help="comma-separated art_ ids")
    parser.add_argument("--code-artifact", required=True)
    parser.add_argument("--parameters", default="{}", help="JSON object")
    parser.add_argument("--random-seed", type=int, default=None)
    parser.add_argument("--status", choices=["succeeded", "failed", "cancelled"], required=True)
    parser.add_argument("--output-artifacts", default="", help="comma-separated art_ ids")
    parser.add_argument("--metrics", default="{}", help="JSON object of numbers")
    args = parser.parse_args()
    try:
        record = create_experiment_record(
            input_artifact_ids=[item for item in args.input_artifacts.split(",") if item],
            code_artifact_id=args.code_artifact,
            parameters=strict_loads(args.parameters),
            random_seed=args.random_seed,
            status=args.status,
            output_artifact_ids=[item for item in args.output_artifacts.split(",") if item],
            metrics=strict_loads(args.metrics),
            project_root=args.project_root,
        )
    except (TypeError, ValueError, json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(record, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
