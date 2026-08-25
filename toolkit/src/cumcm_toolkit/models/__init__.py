"""Public model capability interfaces."""

from collections.abc import Mapping

from .specifications import (
    CapabilityRegistry,
    ModelSpec,
    get_spec,
    list_capabilities,
    register_spec,
)


def execute(model_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    """Lazily dispatch a registered model without coupling legacy imports to the repo."""
    from .execution import execute as dispatch

    return dispatch(model_id, payload)


__all__ = [
    "CapabilityRegistry",
    "ModelSpec",
    "execute",
    "get_spec",
    "list_capabilities",
    "register_spec",
]
