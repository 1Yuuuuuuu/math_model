import pytest

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
