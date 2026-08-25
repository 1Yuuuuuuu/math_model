"""Public dispatcher for registered model specifications."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from .result import build_success_result
from .specifications import get_spec


def execute(model_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    """Execute a registered model using an isolated payload and JSON result contract."""
    try:
        spec = get_spec(model_id)
    except KeyError as exc:
        raise ValueError(f"{model_id}: specification stage failed: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise ValueError(f"{model_id}: payload stage failed: payload must be a mapping")
    missing = [field for field in spec.payload_fields if field not in payload]
    if missing:
        raise ValueError(
            f"{model_id}: payload fields stage failed: missing {', '.join(missing)}"
        )
    try:
        isolated_payload = copy.deepcopy(dict(payload))
    except ValueError as exc:
        raise ValueError(f"{model_id}: payload stage failed: cannot copy payload: {exc}") from exc

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
