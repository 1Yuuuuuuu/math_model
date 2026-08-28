import pytest

from cumcm_toolkit.models.estimator_factories import (
    decision_tree_factory,
    kmeans_factory,
    linear_regression_factory,
)
from cumcm_toolkit.models.registry import get_model, list_models, register_model


def test_register_and_list() -> None:
    register_model("probe-model", lambda: object())
    assert "probe-model" in list_models()
    assert get_model("probe-model") is not None


def test_unknown_model_fails_closed() -> None:
    with pytest.raises(KeyError):
        get_model("does-not-exist")


def test_builtin_models_registered() -> None:
    for name in ("linear-regression", "decision-tree", "kmeans"):
        assert name in list_models()


def test_legacy_registry_reuses_neutral_builtin_factories() -> None:
    """Duplicated nested constructors would let legacy and packaged semantics drift."""
    assert get_model("linear-regression") is linear_regression_factory
    assert get_model("decision-tree") is decision_tree_factory
    assert get_model("kmeans") is kmeans_factory


def test_registration_preserves_public_overwrite_behavior() -> None:
    """Changing registration to reject overwrite would break the legacy registry contract."""
    first = lambda: "first"
    second = lambda: "second"
    register_model("overwrite-probe", first)
    register_model("overwrite-probe", second)

    assert get_model("overwrite-probe") is second
