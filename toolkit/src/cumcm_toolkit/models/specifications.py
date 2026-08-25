"""Capability registry for model execution specifications."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


_EXECUTORS = frozenset(
    {
        "evaluation",
        "optimization",
        "forecasting",
        "data-processing",
        "statistics",
        "supervised",
        "clustering",
    }
)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class ModelSpec:
    """The registered execution contract for one model capability."""

    model_id: str
    executor: str
    knowledge_card: str
    deterministic: bool
    seed_supported: bool
    payload_fields: tuple[str, ...]
    function: Callable[[Mapping[str, object]], Mapping[str, object]]


class CapabilityRegistry:
    """A registry that admits only documented, reproducible capabilities."""

    def __init__(self, *, repository_root: Path) -> None:
        self._repository_root = Path(repository_root)
        self._specs: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> None:
        if not isinstance(spec, ModelSpec):
            raise ValueError("specification must be a ModelSpec")
        if not isinstance(spec.model_id, str) or not spec.model_id:
            raise ValueError("model_id must be a non-empty string")
        if not isinstance(spec.knowledge_card, str) or not spec.knowledge_card:
            raise ValueError(f"model {spec.model_id}: knowledge_card must be a non-empty string")
        if not isinstance(spec.deterministic, bool) or not isinstance(spec.seed_supported, bool):
            raise ValueError(f"model {spec.model_id}: reproducibility declarations must be booleans")
        if not isinstance(spec.payload_fields, tuple) or any(
            not isinstance(field, str) or not field for field in spec.payload_fields
        ):
            raise ValueError(f"model {spec.model_id}: payload_fields must be a tuple of strings")
        if spec.model_id in self._specs:
            raise ValueError(f"duplicate model_id: {spec.model_id}")
        if spec.executor not in _EXECUTORS:
            raise ValueError(f"unknown executor: {spec.executor}")
        if not spec.deterministic and not spec.seed_supported:
            raise ValueError(
                f"model {spec.model_id}: non-deterministic capabilities must support a seed"
            )
        if not callable(spec.function):
            raise ValueError(f"model {spec.model_id}: function must be callable")

        card_path = (self._repository_root / spec.knowledge_card).resolve()
        root = self._repository_root.resolve()
        if not card_path.is_relative_to(root) or not card_path.is_file():
            raise ValueError(f"knowledge card does not exist: {spec.knowledge_card}")
        self._specs[spec.model_id] = spec

    def get(self, model_id: str) -> ModelSpec:
        try:
            return self._specs[model_id]
        except KeyError as exc:
            raise KeyError(f"unknown model_id: {model_id}") from exc

    def list_capabilities(self) -> list[dict[str, object]]:
        """Return sorted, isolated public descriptions without implementation functions."""
        return [
            copy.deepcopy(
                {
                    "model_id": spec.model_id,
                    "executor": spec.executor,
                    "knowledge_card": spec.knowledge_card,
                    "deterministic": spec.deterministic,
                    "seed_supported": spec.seed_supported,
                    "payload_fields": spec.payload_fields,
                }
            )
            for _, spec in sorted(self._specs.items())
        ]


_REGISTRY = CapabilityRegistry(repository_root=_PROJECT_ROOT)


def register_spec(spec: ModelSpec) -> None:
    """Register a model specification in the process-wide capability registry."""
    _REGISTRY.register(spec)


def get_spec(model_id: str) -> ModelSpec:
    """Return a registered model specification or raise ``KeyError`` internally."""
    return _REGISTRY.get(model_id)


def list_capabilities() -> list[dict[str, object]]:
    """Return isolated public capability descriptions from the global registry."""
    return _REGISTRY.list_capabilities()


from .executors.evaluation import execute_ahp, execute_entropy_weight, execute_grey_relational, execute_topsis
from .executors.optimization import (
    execute_integer_programming,
    execute_linear_programming,
    execute_nonlinear_programming,
)


register_spec(
    ModelSpec(
        "topsis",
        "evaluation",
        "shared/knowledge/model-cards/evaluation/topsis.md",
        True,
        False,
        ("matrix", "criteria"),
        execute_topsis,
    )
)
register_spec(
    ModelSpec(
        "linear-programming",
        "optimization",
        "shared/knowledge/model-cards/optimization/linear-programming.md",
        True,
        False,
        ("objective", "sense", "bounds"),
        execute_linear_programming,
    )
)
register_spec(
    ModelSpec(
        "integer-programming",
        "optimization",
        "shared/knowledge/model-cards/optimization/integer-programming.md",
        True,
        False,
        ("objective", "sense", "bounds", "integrality"),
        execute_integer_programming,
    )
)
register_spec(
    ModelSpec(
        "nonlinear-programming",
        "optimization",
        "shared/knowledge/model-cards/optimization/nonlinear-programming.md",
        True,
        False,
        ("objective", "initial", "bounds", "sense", "constraints"),
        execute_nonlinear_programming,
    )
)
register_spec(
    ModelSpec(
        "ahp",
        "evaluation",
        "shared/knowledge/model-cards/evaluation/ahp.md",
        True,
        False,
        ("pairwise_matrix",),
        execute_ahp,
    )
)
register_spec(
    ModelSpec(
        "grey-relational-analysis",
        "evaluation",
        "shared/knowledge/model-cards/evaluation/grey-relational.md",
        True,
        False,
        ("reference", "comparatives"),
        execute_grey_relational,
    )
)
register_spec(
    ModelSpec(
        "entropy-weight",
        "evaluation",
        "shared/knowledge/model-cards/evaluation/entropy-weight.md",
        True,
        False,
        ("matrix", "criteria"),
        execute_entropy_weight,
    )
)
