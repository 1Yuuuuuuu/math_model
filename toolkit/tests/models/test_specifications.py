from __future__ import annotations

import numpy as np
import pytest

from cumcm_toolkit.models.executors.base import numeric_array, required_mapping
from cumcm_toolkit.models.specifications import CapabilityRegistry, ModelSpec


CARD = "shared/knowledge/model-cards/statistics/anova.md"


@pytest.mark.parametrize(
    ("bad", "ndim"),
    [
        ([], 1),
        ([[1, 2], [3]], 2),
        ([True, False], 1),
        ([1, np.nan], 1),
        ([1 + 2j], 1),
        ("1,2", 1),
        ({"value": 1}, 1),
    ],
)
def test_numeric_array_rejects_unsafe_inputs_with_field_name(
    bad: object, ndim: int
) -> None:
    """Removing any input guard must reject malformed numeric payloads."""
    with pytest.raises(ValueError, match="x"):
        numeric_array({"x": bad}, "x", ndim=ndim)


def test_numeric_array_requires_present_field_and_exact_dimension() -> None:
    """Removing required-field or dimension validation must fail before an executor runs."""
    with pytest.raises(ValueError, match="x"):
        numeric_array({}, "x")
    with pytest.raises(ValueError, match="x"):
        numeric_array({"x": [[1, 2]]}, "x", ndim=1)


@pytest.mark.parametrize("min_size", [0, -1])
def test_numeric_array_never_allows_an_empty_array(min_size: int) -> None:
    """Relaxing min_size must not allow an executor to receive empty numeric input."""
    with pytest.raises(ValueError, match="x"):
        numeric_array({"x": []}, "x", min_size=min_size)


def test_required_mapping_rejects_missing_and_non_mapping_values() -> None:
    """Removing mapping validation would allow malformed nested executor payloads."""
    with pytest.raises(ValueError, match="options"):
        required_mapping({}, "options")
    with pytest.raises(ValueError, match="options"):
        required_mapping({"options": []}, "options")


def test_registry_rejects_missing_knowledge_card(tmp_path) -> None:
    registry = CapabilityRegistry(repository_root=tmp_path)
    spec = ModelSpec("probe-model", "statistics", "missing.md", True, False, ("x",), lambda p: {})

    with pytest.raises(ValueError, match="knowledge card"):
        registry.register(spec)


def test_registry_rejects_duplicate_model_id(project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)
    spec = ModelSpec("probe-model", "statistics", CARD, True, False, ("x",), lambda p: {})
    registry.register(spec)

    with pytest.raises(ValueError, match="duplicate model_id"):
        registry.register(spec)


def test_registry_rejects_unknown_executor_and_unseeded_random_capability(project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)

    with pytest.raises(ValueError, match="executor"):
        registry.register(ModelSpec("bad-executor", "unknown", CARD, True, False, (), lambda p: {}))
    with pytest.raises(ValueError, match="seed"):
        registry.register(ModelSpec("unseeded-random", "statistics", CARD, False, False, (), lambda p: {}))


@pytest.mark.parametrize(
    "spec",
    [
        ModelSpec("bad-determinism", "statistics", CARD, "yes", False, (), lambda p: {}),
        ModelSpec("bad-fields", "statistics", CARD, True, False, ["x"], lambda p: {}),
    ],
)
def test_registry_rejects_malformed_capability_declarations(project_root, spec) -> None:
    """Weak metadata validation could admit declarations the dispatcher cannot enforce."""
    registry = CapabilityRegistry(repository_root=project_root)

    with pytest.raises(ValueError):
        registry.register(spec)


def test_registry_allows_seeded_random_and_exposes_isolated_capabilities(project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)
    registry.register(ModelSpec("z-model", "statistics", CARD, False, True, ("x",), lambda p: {}))
    registry.register(ModelSpec("a-model", "statistics", CARD, True, True, ("y",), lambda p: {}))

    capabilities = registry.list_capabilities()

    assert [item["model_id"] for item in capabilities] == ["a-model", "z-model"]
    assert all("function" not in item for item in capabilities)
    capabilities[0]["payload_fields"] = ("tampered",)
    assert registry.get("a-model").payload_fields == ("y",)
