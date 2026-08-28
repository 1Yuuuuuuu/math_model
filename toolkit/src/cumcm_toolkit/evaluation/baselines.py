from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np

from cumcm_toolkit.evaluation.metrics import regression_metrics
from cumcm_toolkit.utils.numbers import ensure_finite, to_python_scalar


def constant_baseline(y: Any, *, strategy: str = "mean") -> dict[str, object]:
    values = np.asarray(y)
    if values.size == 0:
        raise ValueError("constant baseline requires non-empty input")
    if strategy == "mean":
        value: object = ensure_finite(float(np.mean(values)), "constant_baseline mean")
    elif strategy == "median":
        value = ensure_finite(float(np.median(values)), "constant_baseline median")
    elif strategy == "majority":
        unique, counts = np.unique(values, return_counts=True)
        value = to_python_scalar(unique[int(np.argmax(counts))])
    else:
        raise ValueError(f"unknown baseline strategy: {strategy}")
    return {"strategy": strategy, "value": value, "fitted": value}


def compare_to_baseline(
    y_true: Any, y_pred: Any, baseline_value: float, *, metric: str = "rmse"
) -> dict[str, object]:
    if metric != "rmse":
        raise ValueError(f"unsupported metric: {metric}")
    baseline_value = ensure_finite(baseline_value, "compare_to_baseline baseline_value")
    model_score = regression_metrics(y_true, y_pred)["rmse"]
    errors = np.asarray(y_true, dtype=float) - baseline_value
    if errors.size == 0:
        raise ValueError("compare_to_baseline requires non-empty input")
    if not np.isfinite(errors).all():
        raise ValueError("compare_to_baseline requires finite values")
    baseline_score = float(np.mean(errors**2)) ** 0.5
    improvement: float | None
    if baseline_score == 0:
        improvement = None
    else:
        improvement = round((baseline_score - model_score) / baseline_score, 6)
    return {
        "metric": metric,
        "model_score": model_score,
        "baseline_score": round(baseline_score, 6),
        "improvement": improvement,
    }


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a constant baseline or compare predictions to one")
    parser.add_argument("--strategy", default=None, help="mean or median")
    parser.add_argument("--y", default=None, help="JSON array of values")
    parser.add_argument("--compare", action="store_true", help="compare model predictions to a constant baseline")
    parser.add_argument("--y-true", default=None, help="JSON array of true values")
    parser.add_argument("--y-pred", default=None, help="JSON array of predicted values")
    parser.add_argument("--baseline-value", type=float, default=None)
    args = parser.parse_args()
    try:
        if args.compare:
            if args.baseline_value is None:
                raise ValueError("--compare requires --baseline-value")
            if args.y_true is None or args.y_pred is None:
                raise ValueError("--compare requires --y-true and --y-pred")
            y_true = json.loads(args.y_true, parse_constant=_reject_nonstandard_json_constant)
            y_pred = json.loads(args.y_pred, parse_constant=_reject_nonstandard_json_constant)
            result: dict[str, object] = compare_to_baseline(y_true, y_pred, args.baseline_value)
        else:
            if args.strategy is None:
                raise ValueError("either --strategy or --compare is required")
            if args.y is None:
                raise ValueError("--strategy requires --y")
            y = json.loads(args.y, parse_constant=_reject_nonstandard_json_constant)
            baseline = constant_baseline(y, strategy=args.strategy)
            result = {"strategy": baseline["strategy"], "value": baseline["value"]}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
