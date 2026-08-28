from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence

import pytest

from cumcm_toolkit.models import execute


EVALUATION_PAYLOAD = {
    "matrix": [[80, 7], [90, 9], [75, 6]],
    "criteria": ["benefit", "cost"],
}
LP_PAYLOAD = {
    "objective": [3, 2],
    "sense": "maximize",
    "bounds": [[0, None], [0, None]],
    "inequality": {
        "matrix": [[1, 1], [1, 0], [0, 1]],
        "upper": [4, 2, 3],
    },
}


def _assert_strict_json_roundtrip(value: object) -> None:
    """Reject non-finite numbers or transport-only differences in an envelope."""
    encoded = json.dumps(value, allow_nan=False)
    assert json.loads(encoded) == value


def _assert_finite_tree(value: object) -> None:
    """Reject a non-finite numeric leaf even if a serializer is later relaxed."""
    if isinstance(value, Mapping):
        for child in value.values():
            _assert_finite_tree(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            _assert_finite_tree(child)
    elif isinstance(value, float):
        assert math.isfinite(value)


def _assert_json_envelopes(*envelopes: dict[str, object]) -> None:
    for envelope in envelopes:
        _assert_finite_tree(envelope)
        _assert_strict_json_roundtrip(envelope)


def _assert_lp_solution_is_feasible(envelope: dict[str, object]) -> list[float]:
    result = envelope["result"]
    assert isinstance(result, dict)
    solution = result["solution"]
    assert isinstance(solution, list)
    assert len(solution) == 2
    x, y = solution
    assert x >= -1e-8
    assert y >= -1e-8
    assert x + y <= 4 + 1e-8
    assert x <= 2 + 1e-8
    assert y <= 3 + 1e-8
    assert result["objective"] == pytest.approx(3 * x + 2 * y)
    feasibility = envelope["diagnostics"]["feasibility"]
    assert feasibility["feasible"] is True
    assert feasibility["max_violation"] <= feasibility["tolerance"]
    return solution


def test_evaluation_pipeline_entropy_weights_feed_topsis() -> None:
    """Breaking weight shape, normalization, or ranking transport breaks the pipeline."""
    weighted = execute("entropy-weight", EVALUATION_PAYLOAD)
    weights = weighted["result"]["weights"]
    ranking = execute("topsis", {**EVALUATION_PAYLOAD, "weights": weights})

    assert len(weights) == len(EVALUATION_PAYLOAD["criteria"])
    assert all(weight >= 0 for weight in weights)
    assert sum(weights) == pytest.approx(1.0)
    assert len(ranking["result"]["closeness"]) == len(EVALUATION_PAYLOAD["matrix"])
    assert sorted(ranking["result"]["ranking"]) == list(
        range(len(EVALUATION_PAYLOAD["matrix"]))
    )
    _assert_json_envelopes(weighted, ranking)


def test_optimization_continuous_and_integer_solutions_are_feasible() -> None:
    """A rounded, sign-flipped, or constraint-violating MILP answer must fail here."""
    continuous = execute("linear-programming", LP_PAYLOAD)
    integer = execute(
        "integer-programming", {**LP_PAYLOAD, "integrality": [1, 1]}
    )

    _assert_lp_solution_is_feasible(continuous)
    integer_solution = _assert_lp_solution_is_feasible(integer)
    assert all(value == pytest.approx(round(value), abs=1e-8) for value in integer_solution)
    assert integer["result"]["objective"] <= continuous["result"]["objective"] + 1e-9
    _assert_json_envelopes(continuous, integer)


def test_forecasts_expose_fitted_future_and_interval_shapes() -> None:
    """Conflating fitted and future regions or dropping ARIMA intervals breaks this contract."""
    series = [10 + 0.5 * index for index in range(30)]
    arima = execute(
        "arima", {"series": series, "order": [1, 1, 0], "forecast_steps": 3}
    )
    smoothing = execute(
        "exponential-smoothing",
        {
            "series": series,
            "forecast_steps": 3,
            "trend": "add",
            "seasonal": None,
        },
    )

    assert len(arima["result"]["fitted"]) == len(series)
    assert len(arima["result"]["forecast"]) == 3
    assert len(arima["result"]["confidence_interval"]) == 3
    assert all(len(interval) == 2 for interval in arima["result"]["confidence_interval"])
    assert len(smoothing["result"]["fitted"]) == len(series)
    assert len(smoothing["result"]["forecast"]) == 3
    _assert_json_envelopes(arima, smoothing)


def test_data_pipeline_normalizes_detects_and_reduces() -> None:
    """Row loss, feature-shaped anomaly masks, or transposed PCA scores break the pipeline."""
    matrix = [[1, 10], [2, 11], [3, 12], [20, 30]]
    normalized = execute("normalization", {"matrix": matrix, "method": "zscore"})
    transformed = normalized["result"]["transformed"]
    reduced = execute(
        "pca", {"matrix": transformed, "components": 1, "standardize": False}
    )
    anomalies = execute("anomaly-detection", {"matrix": matrix, "method": "iqr"})

    assert len(transformed) == len(matrix)
    assert all(len(row) == len(matrix[0]) for row in transformed)
    assert len(reduced["result"]["transformed"]) == len(matrix)
    assert all(len(row) == 1 for row in reduced["result"]["transformed"])
    assert len(reduced["result"]["components"]) == 1
    assert len(reduced["result"]["components"][0]) == len(matrix[0])
    assert anomalies["result"]["mask"] == [False, False, False, True]
    assert anomalies["result"]["anomaly_indices"] == [3]
    _assert_json_envelopes(normalized, reduced, anomalies)


def test_statistics_pipeline_reports_complete_finite_summaries() -> None:
    """Losing a statistic or violating ANOVA decomposition breaks the public summaries."""
    correlation = execute(
        "correlation-analysis",
        {"x": [1, 2, 3, 4], "y": [2, 4, 6, 8], "method": "pearson"},
    )
    hypothesis = execute(
        "parametric-test",
        {
            "test": "independent-t",
            "sample_a": [1, 2, 3],
            "sample_b": [4, 5, 6],
            "equal_variance": False,
        },
    )
    anova = execute("anova", {"groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})

    assert correlation["result"]["coefficient"] == pytest.approx(1.0)
    assert 0 <= correlation["result"]["p_value"] <= 1
    assert set(hypothesis["result"]) >= {
        "statistic",
        "p_value",
        "degrees_freedom",
        "mean_difference",
        "effect_size",
    }
    assert 0 <= hypothesis["result"]["p_value"] <= 1
    assert anova["result"]["df_between"] == 2
    assert anova["result"]["df_within"] == 6
    assert anova["result"]["ss_total"] == pytest.approx(
        anova["result"]["ss_between"] + anova["result"]["ss_within"]
    )
    assert 0 <= anova["result"]["eta_squared"] <= 1
    _assert_json_envelopes(correlation, hypothesis, anova)


def test_supervised_and_clustering_outputs_are_finite_json() -> None:
    """Wrong class axes or counting DBSCAN noise as a cluster breaks this scenario."""
    classified = execute(
        "logistic-regression",
        {
            "X": [[0], [1], [2], [3]],
            "y": [0, 0, 1, 1],
            "predict_X": [[1.5]],
            "seed": 7,
        },
    )
    clustered = execute(
        "dbscan",
        {
            "X": [[0, 0], [0, 0.1], [10, 10]],
            "params": {"eps": 0.3, "min_samples": 2},
            "standardized": False,
        },
    )

    probabilities = classified["result"]["probabilities"]
    assert len(classified["result"]["classes"]) == 2
    assert len(probabilities) == 1
    assert len(probabilities[0]) == 2
    assert sum(probabilities[0]) == pytest.approx(1.0)
    assert len(clustered["result"]["labels"]) == 3
    assert clustered["result"]["cluster_count"] == 1
    assert clustered["result"]["noise_count"] == 1
    _assert_json_envelopes(classified, clustered)
