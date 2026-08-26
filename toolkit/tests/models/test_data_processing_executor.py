"""Public behavior tests for data-processing model execution."""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


def test_zscore_normalization_records_parameters() -> None:
    """Changing the population scale or constant-column handling breaks this output."""
    result = execute("normalization", {"matrix": [[1, 10], [3, 10]], "method": "zscore"})

    np.testing.assert_allclose(result["result"]["transformed"], [[-1, 0], [1, 0]])
    assert result["result"]["mean"] == [2.0, 10.0]
    assert result["result"]["scale"] == [1.0, 0.0]
    assert "constant column 1" in " ".join(result["warnings"])


@pytest.mark.parametrize(
    ("method", "expected", "statistic"),
    [
        ("minmax", [[0.0], [0.5], [1.0]], {"min": [1.0], "range": [4.0]}),
        ("robust", [[-1.0], [0.0], [1.0]], {"median": [3.0], "iqr": [2.0]}),
    ],
)
def test_normalization_uses_requested_statistics(
    method: str, expected: list[list[float]], statistic: dict[str, list[float]]
) -> None:
    """Replacing a robust/min-max statistic with z-score changes these hand-calculated values."""
    result = execute("normalization", {"matrix": [[1], [3], [5]], "method": method})

    np.testing.assert_allclose(result["result"]["transformed"], expected)
    for key, value in statistic.items():
        assert result["result"][key] == value


def test_normalization_preserves_unselected_columns() -> None:
    """Transforming every column despite selection would alter the second column."""
    result = execute(
        "normalization",
        {"matrix": [[1, 10], [3, 20]], "method": "minmax", "columns": [0]},
    )

    assert result["result"]["transformed"] == [[0.0, 10.0], [1.0, 20.0]]
    assert result["parameters"]["columns"] == [0]


@pytest.mark.parametrize(
    ("policy", "expected_rows", "summary_field"),
    [
        ("drop-rows", [[0.0], [0.5], [1.0]], "dropped_rows"),
        ("column-mean", [[0.0], [0.5], [0.5], [1.0]], "filled_rows"),
    ],
)
def test_normalization_handles_nan_only_with_explicit_policy(
    policy: str, expected_rows: list[list[float]], summary_field: str
) -> None:
    """Ignoring NaN or applying the wrong row policy changes retained transformed values."""
    result = execute(
        "normalization",
        {"matrix": [[1], [np.nan], [3], [5]], "method": "minmax", "missing_policy": policy},
    )

    np.testing.assert_allclose(result["result"]["transformed"], expected_rows)
    assert result["input_summary"]["missing_rows"] == [1]
    assert result["input_summary"][summary_field] == [1]


def test_missing_data_defaults_to_reject_and_infinity_is_never_missing() -> None:
    """Treating omitted policy or infinity as fillable would permit invalid input."""
    with pytest.raises(ValueError, match="missing_policy"):
        execute("normalization", {"matrix": [[1], [np.nan]]})
    with pytest.raises(ValueError, match="matrix"):
        execute(
            "normalization",
            {"matrix": [[1], [np.inf]], "missing_policy": "drop-rows"},
        )


def test_pchip_interpolation_marks_explicit_extrapolation() -> None:
    """Dropping the extrapolation marker would conceal the unsupported value at -1."""
    result = execute(
        "interpolation",
        {
            "x": [0, 1, 2],
            "y": [0, 1, 4],
            "new_x": [-1, 1.5],
            "method": "pchip",
            "extrapolation": "allow",
        },
    )

    assert result["result"]["extrapolated"] == [True, False]
    assert len(result["result"]["values"]) == 2


def test_interpolation_rejects_unsorted_or_duplicate_x_and_default_extrapolation() -> None:
    """Sorting or accepting repeated nodes would change the interpolation problem."""
    for x in ([0, 0, 1], [0, 2, 1]):
        with pytest.raises(ValueError, match="x"):
            execute("interpolation", {"x": x, "y": [0, 1, 2], "new_x": [0.5]})
    with pytest.raises(ValueError, match="extrapolation"):
        execute("interpolation", {"x": [0, 1], "y": [0, 1], "new_x": [-1]})


@pytest.mark.parametrize(
    ("method", "x", "y"),
    [
        ("linear", [0, 1], [0, 2]),
        ("nearest", [0, 1], [0, 2]),
        ("cubic", [0, 1, 2, 3], [0, 1, 4, 9]),
        ("pchip", [0, 1], [0, 2]),
    ],
)
def test_interpolation_methods_return_one_value_per_requested_point(
    method: str, x: list[float], y: list[float]
) -> None:
    """A method returning a scalar or wrong-sized array breaks the request-to-result mapping."""
    result = execute("interpolation", {"x": x, "y": y, "new_x": [0.25, 0.75], "method": method})

    assert len(result["result"]["values"]) == 2
    assert result["result"]["extrapolated"] == [False, False]


def test_interpolation_enforces_method_sample_boundary_and_paired_missing_rows() -> None:
    """Cubic needs four nodes and missing-pair removal must delete both x and y values."""
    with pytest.raises(ValueError, match="cubic"):
        execute("interpolation", {"x": [0, 1, 2], "y": [0, 1, 4], "new_x": [0.5], "method": "cubic"})

    result = execute(
        "interpolation",
        {
            "x": [0, np.nan, 2],
            "y": [0, 99, 4],
            "new_x": [1],
            "missing_policy": "drop-rows",
        },
    )
    assert result["result"]["values"] == [2.0]
    assert result["input_summary"]["dropped_rows"] == [1]


def test_iqr_anomaly_detection_finds_outlier() -> None:
    """Changing zero-IQR handling would hide the 10 in this otherwise constant column."""
    result = execute("anomaly-detection", {"matrix": [[1], [1], [1], [10]], "method": "iqr"})

    assert result["result"]["anomaly_indices"] == [3]
    assert result["result"]["count"] == 1
    assert result["result"]["mask"] == [[False], [False], [False], [True]]


def test_zscore_anomaly_detection_handles_zero_scale_without_nan() -> None:
    """Dividing a constant column by zero would return NaN instead of a clean all-false mask."""
    result = execute("anomaly-detection", {"matrix": [[7], [7], [7]], "method": "zscore"})

    assert result["result"]["mask"] == [[False], [False], [False]]
    assert "zero scale column 0" in " ".join(result["warnings"])


def test_isolation_forest_is_repeatable_for_the_same_seed_and_rejects_random_state() -> None:
    """Passing uncontrolled randomness or a hidden random_state would make results irreproducible."""
    payload = {
        "matrix": [[0], [0.1], [0.2], [10]],
        "method": "isolation-forest",
        "contamination": 0.25,
        "seed": 17,
    }
    first = execute("anomaly-detection", payload)
    second = execute("anomaly-detection", payload)

    assert first["result"] == second["result"]
    assert first["reproducibility"] == {"seed": 17, "deterministic": True}
    with pytest.raises(ValueError, match="random_state"):
        execute("anomaly-detection", {**payload, "random_state": 3})


@pytest.mark.parametrize(
    ("model_id", "payload"),
    [
        ("normalization", {"matrix": [[1]], "method": "unknown"}),
        ("interpolation", {"x": [0, 1], "y": [0, 1], "new_x": [0], "method": "unknown"}),
        ("anomaly-detection", {"matrix": [[1]], "method": "unknown"}),
    ],
)
def test_data_processing_models_reject_unknown_methods(model_id: str, payload: dict[str, object]) -> None:
    """Silently selecting a default method for a typo would change data processing semantics."""
    with pytest.raises(ValueError, match="method"):
        execute(model_id, payload)


def test_data_processing_models_are_registered_and_preserve_finite_json_input() -> None:
    """Undocumented registration, mutation, or non-JSON output breaks safe dispatch."""
    cases = {
        "normalization": {"matrix": [[1, 2], [3, 4]]},
        "interpolation": {"x": [0, 1], "y": [0, 1], "new_x": [0.5]},
        "anomaly-detection": {"matrix": [[1], [2]], "method": "zscore"},
    }
    capabilities = {item["model_id"]: item for item in list_capabilities()}
    for model_id, payload in cases.items():
        before = copy.deepcopy(payload)
        result = execute(model_id, payload)

        assert payload == before
        assert json.loads(json.dumps(result, allow_nan=False)) == result
        assert get_spec(model_id).function is not None
        assert capabilities[model_id]["executor"] == "data-processing"
        assert capabilities[model_id]["deterministic"] is True
