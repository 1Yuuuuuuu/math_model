from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from jsonschema import ValidationError

from scripts.validate_contracts import load_json, make_validator


_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCHEMA_PATH = _PROJECT_ROOT / "shared/contracts/model-execution.schema.json"


def normalize_json(value: object, field: str) -> object:
    if isinstance(value, np.ndarray):
        return normalize_json(value.tolist(), field)
    if isinstance(value, np.generic):
        return normalize_json(value.item(), field)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must contain only finite numbers")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{field} must use string keys")
        return {
            key: normalize_json(item, f"{field}.{key}") for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_json(item, field) for item in value]
    raise ValueError(f"{field} contains a non-JSON value: {type(value).__name__}")


def build_success_result(
    model_id: str,
    executor: str,
    raw: Mapping[str, object],
    *,
    deterministic: bool,
) -> dict[str, object]:
    try:
        warnings = raw["warnings"]
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("raw result warnings must be an array of strings")
        envelope = {
            "schema_version": "1.0",
            "status": "succeeded",
            "model_id": model_id,
            "executor": executor,
            "parameters": raw["parameters"],
            "input_summary": raw["input_summary"],
            "result": raw["result"],
            "diagnostics": raw["diagnostics"],
            "warnings": sorted(set(warnings)),
            "reproducibility": {
                "seed": raw["seed"],
                "deterministic": deterministic,
            },
        }
    except KeyError as exc:
        raise ValueError(f"raw result is missing required field: {exc.args[0]}") from exc
    except ValueError:
        raise
    except TypeError as exc:
        raise ValueError("raw result warnings must be an iterable of strings") from exc

    if not all(isinstance(warning, str) for warning in envelope["warnings"]):
        raise ValueError("raw result warnings must contain only strings")

    normalized = normalize_json(envelope, "result")
    try:
        make_validator(load_json(_SCHEMA_PATH)).validate(normalized)
    except ValidationError as exc:
        raise ValueError(f"model execution result violates its contract: {exc.message}") from exc

    return json.loads(json.dumps(normalized, allow_nan=False))
