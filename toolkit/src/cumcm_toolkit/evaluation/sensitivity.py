from __future__ import annotations

import argparse
import json
import math
from typing import Any, Callable

from cumcm_toolkit.experiments.manifest import utc_now_rfc3339  # 复用 Phase 1 时间工具


def sensitivity_report(
    *,
    base_params: dict[str, float],
    perturb: dict[str, list[float]],
    evaluate: Callable[[dict[str, float]], float],
) -> dict[str, object]:
    warnings: list[str] = []
    parameters: dict[str, object] = {}
    for name, values in perturb.items():
        if name not in base_params:
            warnings.append(f"perturbed parameter not in base_params: {name}")
            continue
        results = []
        ok_points = 0
        for value in values:
            candidate = dict(base_params)
            candidate[name] = value
            try:
                result = float(evaluate(candidate))
                if not math.isfinite(result):
                    raise ValueError("non-finite result")
                results.append(round(result, 6))
                ok_points += 1
            except Exception as exc:  # noqa: BLE001 - tolerate single-point failures
                results.append(None)
                warnings.append(f"{name}={value}: {exc}")
        if ok_points == 0:
            raise ValueError(f"no sensitivity point succeeded for parameter {name}")
        finite = [r for r in results if r is not None]
        parameters[name] = {
            "base": round(float(base_params[name]), 6),
            "values": values,
            "results": results,
            "min": min(finite),
            "max": max(finite),
            "range": round(max(finite) - min(finite), 6),
        }
    if not parameters:
        raise ValueError("no parameters perturbed")
    ranges = {name: parameters[name]["range"] for name in parameters}
    dominant = max(ranges, key=ranges.get)
    if max(ranges.values()) <= 1e-9:
        conclusion = "stable"
    else:
        others = ", ".join(f"{k}={v}" for k, v in sorted(ranges.items()) if k != dominant)
        conclusion = f"{dominant} dominates (range {ranges[dominant]}; others {others or 'none'})"
    return {
        "parameters": parameters,
        "conclusion": conclusion,
        "generated_at": utc_now_rfc3339(),
        "warnings": warnings,
    }


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def _validate_report_contract(payload: Any) -> None:
    """Validate the sensitivity report input contract shape.

    Matches the ``sensitivity_report`` signature: ``base_params`` is an
    object of numbers and ``perturb`` an object of number lists. No
    evaluation is performed (the CLI cannot inject an ``evaluate``
    callback).
    """
    if not isinstance(payload, dict):
        raise ValueError("sensitivity input must be a JSON object with base_params and perturb")
    base_params = payload.get("base_params")
    perturb = payload.get("perturb")
    if not isinstance(base_params, dict):
        raise ValueError("base_params must be an object of numbers")
    if not isinstance(perturb, dict):
        raise ValueError("perturb must be an object of number lists")
    for name, value in base_params.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"base_params.{name} must be a number")
    for name, values in perturb.items():
        if not isinstance(values, list):
            raise ValueError(f"perturb.{name} must be a list of numbers")
        for index, value in enumerate(values):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"perturb.{name}[{index}] must be a number")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a sensitivity report input contract (no evaluation)")
    parser.add_argument("--validate", required=True, help="JSON object with base_params and perturb")
    args = parser.parse_args()
    try:
        payload = json.loads(args.validate, parse_constant=_reject_nonstandard_json_constant)
        _validate_report_contract(payload)
        result: dict[str, object] = {"status": "ok", "valid": True}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
