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
    assert result["result"]["mask"] == [False, False, False, True]
    assert result["result"]["cell_mask"] == [[False], [False], [False], [True]]


def test_anomaly_detection_exposes_row_mask_and_only_rule_based_cell_mask() -> None:
    """Publishing a cell mask as the public mask breaks row-level anomaly consumers."""
    result = execute(
        "anomaly-detection",
        {"matrix": [[1, 1], [1, 1], [1, 1], [10, 1]], "method": "iqr"},
    )

    row_mask = result["result"]["mask"]
    assert len(row_mask) == 4
    assert all(type(value) is bool for value in row_mask)
    assert row_mask == [False, False, False, True]
    assert result["result"]["anomaly_indices"] == [index for index, value in enumerate(row_mask) if value]
    assert result["result"]["count"] == sum(row_mask)
    assert result["result"]["cell_mask"] == [
        [False, False],
        [False, False],
        [False, False],
        [True, False],
    ]
    isolation = execute(
        "anomaly-detection",
        {
            "matrix": [[0, 0], [0.1, 0.1], [10, 10]],
            "method": "isolation-forest",
            "contamination": 0.34,
        },
    )
    assert "cell_mask" not in isolation["result"]


@pytest.mark.parametrize(
    ("model_id", "payload"),
    [
        ("normalization", {"matrix": [[1]], "methd": "zscore"}),
        ("interpolation", {"x": [0, 1], "y": [0, 1], "new_x": [0.5], "methd": "linear"}),
        ("anomaly-detection", {"matrix": [[1]], "methd": "iqr"}),
    ],
)
def test_data_processing_models_reject_unknown_payload_fields(
    model_id: str, payload: dict[str, object]
) -> None:
    """Ignoring a misspelled option would silently select an unintended default."""
    with pytest.raises(ValueError, match="methd"):
        execute(model_id, payload)


def test_zscore_anomaly_detection_handles_zero_scale_without_nan() -> None:
    """Dividing a constant column by zero would return NaN instead of a clean all-false mask."""
    result = execute("anomaly-detection", {"matrix": [[7], [7], [7]], "method": "zscore"})

    assert result["result"]["mask"] == [False, False, False]
    assert result["result"]["cell_mask"] == [[False], [False], [False]]
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


def test_pca_returns_scores_variance_and_explicit_component_loadings() -> None:
    """Dropping centering/PCA or confusing scores with component axes breaks reconstruction."""
    matrix = [[1, 2], [2, 4], [3, 6]]
    result = execute("pca", {"matrix": matrix, "components": 1, "standardize": True})

    output = result["result"]
    assert np.asarray(output["transformed"]).shape == (3, 1)
    assert np.asarray(output["components"]).shape == (1, 2)
    assert np.asarray(output["loadings"]).shape == (2, 1)
    assert output["explained_variance_ratio"][0] == pytest.approx(1.0)
    assert output["cumulative_explained_variance_ratio"] == pytest.approx([1.0])
    reconstructed = np.asarray(output["transformed"]) @ np.asarray(output["components"]) + np.asarray(output["mean"])
    np.testing.assert_allclose(reconstructed, [[-1.224744871, -1.224744871], [0, 0], [1.224744871, 1.224744871]])
    np.testing.assert_allclose(np.abs(output["loadings"]), np.sqrt(output["explained_variance"]) * np.abs(output["components"]).T)


@pytest.mark.parametrize("components", [True, False, 0, 3])
def test_pca_rejects_boolean_or_out_of_range_component_counts(components: object) -> None:
    """Accepting bools or invalid ranks would dispatch an undefined dimensionality reduction."""
    with pytest.raises(ValueError, match="components"):
        execute("pca", {"matrix": [[1, 2], [3, 4]], "components": components, "standardize": False})


def test_pca_preserves_unstandardized_scale_when_requested() -> None:
    """Always standardizing would turn this high-variance first feature into equal variance."""
    result = execute("pca", {"matrix": [[0, 0], [10, 1], [20, 2]], "components": 1, "standardize": False})

    assert result["result"]["standardization"] == {"applied": False}
    assert abs(result["result"]["components"][0][0]) > abs(result["result"]["components"][0][1])


def test_pca_standardization_records_zero_scale_column_as_zero() -> None:
    """Dividing a constant feature by zero must not leak NaN into the PCA result."""
    result = execute(
        "pca", {"matrix": [[1, 7], [2, 7], [3, 7]], "components": 1, "standardize": True}
    )

    assert result["result"]["standardization"]["scale"] == [pytest.approx(0.816496580927726), 1.0]
    assert "constant column 1" in " ".join(result["warnings"])
    assert all(np.all(np.isfinite(value)) for value in result["result"].values() if isinstance(value, list))


def test_pca_rejects_all_constant_data_and_insufficient_sample_variance() -> None:
    """Returning undefined explained variance for a zero-variance or one-row fit is invalid."""
    for matrix in ([[7, 7], [7, 7]], [[1, 2]]):
        with pytest.raises(ValueError, match="variance"):
            execute("pca", {"matrix": matrix, "components": 1, "standardize": True})


@pytest.mark.parametrize(
    "payload",
    [
        {"matrix": [[1, np.nan], [2, 3]], "components": 1, "standardize": True},
        {"matrix": [[1, np.inf], [2, 3]], "components": 1, "standardize": True},
        {"matrix": [[1, 2], [3, 4]], "components": 1, "standardize": 1},
        {"matrix": [[1, 2], [3, 4]], "components": 1, "standardize": False, "unexpected": True},
    ],
)
def test_pca_rejects_nonfinite_or_unknown_payload_values(payload: dict[str, object]) -> None:
    """Missing, infinite, wrongly typed, and misspelled fields must fail closed."""
    with pytest.raises(ValueError):
        execute("pca", payload)


@pytest.mark.parametrize(
    ("missing_policy", "expected_rows", "summary_field"),
    [
        ("drop-rows", 2, "dropped_rows"),
        ("column-mean", 3, "filled_rows"),
    ],
)
def test_pca_reuses_data_processing_missing_row_policies(
    missing_policy: str, expected_rows: int, summary_field: str
) -> None:
    """A different NaN policy would lose the original row lineage established by Task 7."""
    result = execute(
        "pca",
        {"matrix": [[1, 2], [np.nan, 3], [3, 4]], "components": 1, "standardize": True, "missing_policy": missing_policy},
    )

    assert len(result["result"]["transformed"]) == expected_rows
    assert result["input_summary"][summary_field] == [1]


def test_pca_is_registered_and_has_finite_json_output() -> None:
    """An unregistered PCA or a non-JSON statistic cannot be safely dispatched by clients."""
    payload = {"matrix": [[1, 2], [2, 3], [3, 4]], "components": 1, "standardize": False}
    before = copy.deepcopy(payload)
    result = execute("pca", payload)
    capability = {item["model_id"]: item for item in list_capabilities()}["pca"]

    assert payload == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert capability == {
        "model_id": "pca",
        "executor": "data-processing",
        "knowledge_card": "shared/knowledge/model-cards/evaluation/pca.md",
        "deterministic": True,
        "seed_supported": False,
        "payload_fields": ("matrix", "components", "standardize"),
    }
    ratios = result["result"]["cumulative_explained_variance_ratio"]
    assert ratios == sorted(ratios)
    assert ratios[-1] <= 1.0
