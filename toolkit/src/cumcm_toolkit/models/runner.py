from __future__ import annotations

import argparse
import json
from typing import Any

from cumcm_toolkit.models.registry import get_model


def run_model(
    name: str,
    X: Any,
    y: Any,
    *,
    seed: int | None = None,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    params = dict(params or {})
    try:
        factory = get_model(name)
        model = factory(seed=seed, params=params)
    except KeyError as exc:
        raise ValueError(f"unknown model: {name}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot construct model {name}: {exc}") from exc
    try:
        model.fit(X, y)
    except Exception as exc:
        raise ValueError(f"model fit failed for {name}: {exc}") from exc
    return {"model": name, "fitted": model, "params": params, "seed": seed}


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit a registered model on JSON data")
    parser.add_argument("--name", required=True, help="registered model name")
    parser.add_argument("--X", required=True, help="JSON array of feature rows")
    parser.add_argument("--y", required=True, help="JSON array of target values")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--params", default=None, help="JSON object of model parameters")
    args = parser.parse_args()
    try:
        X = json.loads(args.X, parse_constant=_reject_nonstandard_json_constant)
        y = json.loads(args.y, parse_constant=_reject_nonstandard_json_constant)
        if not isinstance(X, list):
            raise ValueError("--X must be a JSON array")
        if not isinstance(y, list):
            raise ValueError("--y must be a JSON array")
        params: dict[str, object] = {}
        if args.params is not None:
            parsed = json.loads(args.params, parse_constant=_reject_nonstandard_json_constant)
            if not isinstance(parsed, dict):
                raise ValueError("--params must be a JSON object")
            params = parsed
        result = run_model(args.name, X, y, seed=args.seed, params=params)
        payload: dict[str, object] = {
            "status": "ok",
            "model": result["model"],
            "params": result["params"],
            "seed": result["seed"],
            "fitted": True,
        }
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
