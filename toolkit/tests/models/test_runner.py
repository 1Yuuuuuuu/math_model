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
