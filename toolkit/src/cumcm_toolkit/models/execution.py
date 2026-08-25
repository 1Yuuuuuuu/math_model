"""Public dispatcher for registered model specifications."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from .result import build_success_result
from .specifications import get_spec


def _plain_json_snapshot(
    value: object,
    *,
    path: str,
    active: set[int],
    depth: int = 0,
) -> object:
    """Copy exact built-in JSON containers without invoking copy protocols."""
    if depth > 64:
        raise ValueError(f"{path or 'payload'}: JSON nesting is too deep")
    value_type = type(value)
    if value is None or value_type in (str, int, float, bool):
        return value
    if value_type not in (dict, list):
        raise ValueError(f"{path or 'payload'}: must contain only plain JSON values")

    identity = id(value)
    if identity in active:
        raise ValueError(f"{path or 'payload'}: JSON structure must not be cyclic")
    active.add(identity)
    try:
        if value_type is list:
            return [
                _plain_json_snapshot(
                    item,
                    path=f"{path}[{index}]",
                    active=active,
                    depth=depth + 1,
                )
                for index, item in enumerate(list.__iter__(value))
            ]

        snapshot: dict[str, object] = {}
        for key, item in dict.items(value):
            if type(key) is not str:
                raise ValueError(f"{path or 'payload'}: JSON object keys must be strings")
            item_path = f"{path}.{key}" if path else key
            snapshot[key] = _plain_json_snapshot(
                item, path=item_path, active=active, depth=depth + 1
            )
        return snapshot
    finally:
        active.remove(identity)


def execute(model_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    """Execute a registered model using an isolated payload and JSON result contract."""
    try:
        spec = get_spec(model_id)
    except KeyError as exc:
        raise ValueError(f"{model_id}: specification stage failed: {exc}") from exc

    if model_id == "nonlinear-programming":
        if type(payload) is not dict:
            raise ValueError(
                f"{model_id}: payload stage failed: payload must be a plain JSON object"
            )
        try:
            isolated_payload = _plain_json_snapshot(
                payload, path="", active=set()
            )
        except ValueError as exc:
            raise ValueError(f"{model_id}: execution stage failed: {exc}") from exc
        assert isinstance(isolated_payload, dict)
    else:
        if not isinstance(payload, Mapping):
            raise ValueError(f"{model_id}: payload stage failed: payload must be a mapping")
        try:
            isolated_payload = copy.deepcopy(dict(payload))
        except ValueError as exc:
            raise ValueError(
                f"{model_id}: payload stage failed: cannot copy payload: {exc}"
            ) from exc

    missing = [field for field in spec.payload_fields if field not in isolated_payload]
    if missing:
        raise ValueError(
            f"{model_id}: payload fields stage failed: missing {', '.join(missing)}"
        )

    try:
        raw = spec.function(isolated_payload)
    except ValueError as exc:
        raise ValueError(f"{model_id}: execution stage failed: {exc}") from exc

    try:
        return build_success_result(
            model_id,
            spec.executor,
            raw,
            deterministic=spec.deterministic,
        )
    except ValueError as exc:
        raise ValueError(f"{model_id}: result stage failed: {exc}") from exc
