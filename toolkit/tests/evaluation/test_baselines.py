import numpy as np
import pytest

from cumcm_toolkit.evaluation.baselines import compare_to_baseline, constant_baseline


def test_constant_baseline_mean_and_majority() -> None:
    assert constant_baseline(np.array([1.0, 2.0, 3.0]))["value"] == pytest.approx(2.0)
    assert constant_baseline(np.array(["a", "a", "b"]), strategy="majority")["value"] == "a"


def test_compare_improvement_positive() -> None:
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.0, 2.0, 3.0, 5.0])  # rmse 0.5
    result = compare_to_baseline(y_true, y_pred, baseline_value=2.5)
    assert result["metric"] == "rmse"
    assert result["model_score"] == pytest.approx(0.5)
    # baseline rmse = sqrt(mean((y_true - 2.5)^2)) = sqrt(1.25) = 1.118034,
    # so improvement = (1.118034 - 0.5) / 1.118034 = 0.552786.
    # (The 0.8 in the original brief corresponds to MSE values, not RMSE.)
    assert result["improvement"] == pytest.approx(0.552786)
