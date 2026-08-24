import numpy as np
import pytest

from cumcm_toolkit.models.runner import run_model


def test_run_linear_regression_recovers_coefficients() -> None:
    rng = np.random.default_rng(7)
    X = rng.normal(size=(60, 2))
    y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + 0.5
    result = run_model("linear-regression", X, y, seed=7)
    fitted = result["fitted"]
    coef = fitted.coef_
    assert np.allclose(coef, [2.0, -1.5], atol=0.05)
    assert result["seed"] == 7
    assert isinstance(result["params"], dict)


def test_run_unknown_model_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_model("nope", np.zeros((3, 2)), np.zeros(3))


def test_params_are_applied_to_model() -> None:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(40, 3))
    y = (X[:, 0] > 0).astype(int)
    tree = run_model("decision-tree", X, y, seed=7, params={"max_depth": 1})
    assert tree["fitted"].get_params()["max_depth"] == 1

    kmeans = run_model("kmeans", X, y, seed=7, params={"n_clusters": 2})
    assert kmeans["fitted"].get_params()["n_clusters"] == 2

    linear = run_model("linear-regression", X, y, params={"fit_intercept": False})
    assert linear["fitted"].get_params()["fit_intercept"] is False
    assert linear["params"] == {"fit_intercept": False}


def test_unsupported_param_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_model("linear-regression", np.zeros((5, 2)), np.zeros(5), params={"bogus": 1})


def test_seed_random_state_conflict_fails() -> None:
    with pytest.raises(ValueError):
        run_model(
            "decision-tree",
            np.zeros((5, 2)),
            np.zeros(5),
            seed=7,
            params={"random_state": 3},
        )


def test_seed_determinism() -> None:
    rng = np.random.default_rng(5)
    X = rng.normal(size=(50, 2))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    first = run_model("decision-tree", X, y, seed=7, params={"max_depth": 2})
    second = run_model("decision-tree", X, y, seed=7, params={"max_depth": 2})
    assert np.array_equal(first["fitted"].predict(X), second["fitted"].predict(X))
