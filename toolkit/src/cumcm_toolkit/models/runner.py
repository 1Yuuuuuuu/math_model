from __future__ import annotations

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
