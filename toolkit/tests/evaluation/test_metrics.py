import numpy as np
import pandas as pd
import pytest

from cumcm_toolkit.evaluation.metrics import (
    check_data_leakage,
    classification_metrics,
    detect_improper_split,
    detect_target_leakage,
    regression_metrics,
)


def test_regression_metrics_values() -> None:
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.0, 2.0, 3.0, 5.0])
    result = regression_metrics(y_true, y_pred)
    assert result["mse"] == pytest.approx(0.25)
    assert result["rmse"] == pytest.approx(0.5)
    assert result["mae"] == pytest.approx(0.25)
    # r2 = 1 - SS_res/SS_tot = 1 - 1/5 = 0.8 (sklearn r2_score)
    assert result["r2"] == pytest.approx(0.8)


def test_regression_metrics_mismatched_length_fails() -> None:
    with pytest.raises(ValueError):
        regression_metrics(np.array([1.0]), np.array([1.0, 2.0]))


def test_classification_metrics_binary() -> None:
    # string labels so the default positive_label="1" matches (int labels
    # would be rejected by sklearn pos_label matching)
    y_true = np.array(["1", "0", "1", "1", "0"])
    y_pred = np.array(["1", "0", "1", "0", "0"])
    result = classification_metrics(y_true, y_pred)
    assert result["accuracy"] == pytest.approx(0.8)
    # TP=2, FP=0, FN=1 -> precision 1.0, recall 2/3, f1 0.8
    assert result["precision"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["f1"] == pytest.approx(0.8)


def test_detect_improper_split_finds_overlap() -> None:
    train = pd.DataFrame({"id": [1, 2, 3], "v": [1.0, 2.0, 3.0]})
    test = pd.DataFrame({"id": [3, 4], "v": [3.0, 4.0]})
    result = detect_improper_split(train, test, ["id"])
    assert result["overlap_rows"] == 1
    assert result["overlapping_keys"] == [3]
    assert "overlap" in result["warning"].lower()


def test_detect_target_leakage_finds_perfect_column() -> None:
    target = pd.Series([1.0, 2.0, 3.0, 4.0])
    # "ok" must NOT be a perfect linear transform of target (0.5 breaks it)
    features = pd.DataFrame({"ok": [0.1, 0.2, 0.3, 0.5], "leak": target * 2})
    leaked = detect_target_leakage(features, target)
    assert leaked == ["leak"]


def test_check_data_leakage_combines_detections() -> None:
    # 3 rows so "x" is not perfectly correlated with the target
    # (any 2-point sample is always perfectly correlated)
    train = pd.DataFrame({"id": [1, 2, 3], "x": [0.1, 0.2, 0.4]})
    test = pd.DataFrame({"id": [3, 4, 5], "x": [0.3, 0.4, 0.5]})
    target = pd.Series([1.0, 2.0, 3.0])
    result = check_data_leakage(train, test, target, key_columns=["id"])
    assert result["improper_split"]["overlap_rows"] == 1
    assert result["target_leakage"] == []
