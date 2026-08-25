"""Public model capability interfaces."""

from .execution import execute
from .specifications import (
    CapabilityRegistry,
    ModelSpec,
    get_spec,
    list_capabilities,
    register_spec,
)

__all__ = [
    "CapabilityRegistry",
    "ModelSpec",
    "execute",
    "get_spec",
    "list_capabilities",
    "register_spec",
]
