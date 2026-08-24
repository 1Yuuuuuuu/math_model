from __future__ import annotations

import math
from typing import Callable

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
