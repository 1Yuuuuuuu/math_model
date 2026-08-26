"""Public behavior tests for correlation and confidence-interval execution."""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest
from scipy import stats

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


@pytest.mark.parametrize("method", ["pearson", "spearman", "kendall"])
def test_pair_correlation_uses_the_requested_scipy_method(method: str) -> None:
    """Replacing a requested rank method with Pearson changes this nonlinear result."""
    x = [1, 2, 3, 4, 5]
    y = [1, 4, 9, 16, 25]
    result = execute("correlation-analysis", {"x": x, "y": y, "method": method})

    expected = {
        "pearson": stats.pearsonr,
        "spearman": stats.spearmanr,
        "kendall": stats.kendalltau,
    }[method](x, y)
    assert result["result"]["coefficient"] == pytest.approx(expected.statistic)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)
    assert result["result"]["sample_size"] == 5


@pytest.mark.parametrize("method", ["pearson", "spearman", "kendall"])
def test_matrix_correlation_returns_symmetric_pairwise_outputs(method: str) -> None:
    """Calculating only one variable pair would omit the matrix-mode contract."""
    result = execute(
        "correlation-analysis",
        {"matrix": [[1, 1, 5], [2, 4, 4], [3, 9, 3], [4, 16, 2]], "method": method},
    )

    coefficient = np.asarray(result["result"]["coefficient"])
    p_value = np.asarray(result["result"]["p_value"])
    sample_size = np.asarray(result["result"]["sample_size"])
    assert coefficient.shape == p_value.shape == sample_size.shape == (3, 3)
    np.testing.assert_allclose(coefficient, coefficient.T)
    np.testing.assert_allclose(p_value, p_value.T)
    assert np.array_equal(sample_size, sample_size.T)
    assert np.all(np.diag(coefficient) == 1.0)
    assert np.all(np.diag(p_value) == 0.0)
    assert np.all(np.diag(sample_size) == 4)


def test_pairwise_missing_data_filters_each_pair_and_reports_counts() -> None:
    """Dropping all rows instead of each pair would change pair (0, 1)'s sample size."""
    result = execute(
        "correlation-analysis",
        {
            "matrix": [[1, 1, np.nan], [2, np.nan, 4], [3, 9, 3], [4, 16, 2]],
            "method": "pearson",
            "missing_policy": "pairwise",
        },
    )

    assert result["result"]["sample_size"] == [[4, 3, 3], [3, 3, 2], [3, 2, 3]]
    assert result["input_summary"]["missing_count"] == 2
    assert result["input_summary"]["pairwise_missing_count"] == [[0, 1, 1], [1, 1, 2], [1, 2, 1]]


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"x": [1, 2], "y": [1, np.nan], "method": "pearson"}, "missing_policy"),
        ({"x": [1, np.inf], "y": [1, 2], "method": "pearson", "missing_policy": "pairwise"}, "x"),
        ({"x": [1, 2], "y": [1, 2], "matrix": [[1, 2], [3, 4]], "method": "pearson"}, "matrix"),
        ({"x": [1, 2], "method": "pearson"}, "x and y"),
        ({"matrix": [[1, 2], [3, 4]], "method": "nope"}, "method"),
        ({"x": [1, 2], "y": [1, 2], "method": "pearson", "typo": 1}, "typo"),
    ],
)
def test_correlation_rejects_ambiguous_or_nonfinite_inputs(payload: dict[str, object], field: str) -> None:
    """Accepting malformed modes or nonfinite values would silently change the analysis."""
    with pytest.raises(ValueError, match=field):
        execute("correlation-analysis", payload)


def test_pair_constant_or_insufficient_samples_fail_without_warning_leakage() -> None:
    """Returning SciPy NaN/warnings conceals an undefined pair correlation."""
    with pytest.raises(ValueError, match="constant"):
        execute("correlation-analysis", {"x": [1, 1, 1], "y": [1, 2, 3], "method": "pearson"})
    with pytest.raises(ValueError, match="at least 2"):
        execute("correlation-analysis", {"x": [1], "y": [1], "method": "pearson"})


def test_matrix_constant_and_short_pairs_are_null_with_structured_diagnostics() -> None:
    """One undefined matrix pair must not prevent independent pairs from being calculated."""
    result = execute(
        "correlation-analysis",
        {
            "matrix": [[1, 1, np.nan], [1, 2, np.nan], [np.nan, 3, 1], [np.nan, 4, 2]],
            "method": "pearson",
            "missing_policy": "pairwise",
        },
    )

    assert result["result"]["coefficient"][0][1] is None
    assert result["result"]["p_value"][0][1] is None
    assert result["result"]["coefficient"][1][2] == pytest.approx(1.0)
    assert result["diagnostics"]["pairs"]["0,1"]["reason"] == "constant_input"
    assert result["diagnostics"]["pairs"]["0,2"]["reason"] == "insufficient_samples"


def test_mean_t_interval_matches_scipy_and_uses_sample_standard_deviation() -> None:
    """Using population variance or a normal critical value changes this interval."""
    sample = [1, 2, 3, 4]
    result = execute("confidence-interval", {"method": "mean-t", "sample": sample, "confidence": 0.95})
    expected = stats.t.interval(0.95, df=3, loc=2.5, scale=np.std(sample, ddof=1) / 2)

    assert result["result"]["estimate"] == pytest.approx(2.5)
    assert result["result"]["lower"] == pytest.approx(expected[0])
    assert result["result"]["upper"] == pytest.approx(expected[1])
    assert result["result"]["sample_size"] == 4


def test_mean_t_zero_variance_returns_a_documented_degenerate_interval() -> None:
    """Dividing by zero for identical observations must not produce a NaN interval."""
    result = execute("confidence-interval", {"method": "mean-t", "sample": [7, 7], "confidence": 0.95})

    assert result["result"]["estimate"] == result["result"]["lower"] == result["result"]["upper"] == 7.0
    assert result["diagnostics"]["standard_error"] == 0.0


def test_mean_t_preserves_a_subnormal_nonzero_sample_variance() -> None:
    """Treating two distinct subnormal observations as identical loses a real uncertainty interval."""
    result = execute(
        "confidence-interval",
        {"method": "mean-t", "sample": [0.0, float.fromhex("0x0.0000000000001p-1022")], "confidence": 0.95},
    )

    assert result["diagnostics"]["standard_error"] > 0.0
    assert result["result"]["lower"] < result["result"]["estimate"] < result["result"]["upper"]


@pytest.mark.parametrize(
    ("successes", "total"),
    [(0, 10), (10, 10), (5, 10)],
)
def test_wilson_interval_stays_in_probability_bounds_and_contains_estimate(
    successes: int, total: int
) -> None:
    """An unstable Wilson formula could emit bounds outside the probability scale."""
    result = execute(
        "confidence-interval",
        {"method": "proportion-wilson", "successes": successes, "total": total, "confidence": 0.95},
    )

    output = result["result"]
    assert 0 <= output["lower"] <= output["estimate"] <= output["upper"] <= 1
    assert output["sample_size"] == total


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"method": "mean-t", "sample": [1], "confidence": 0.95}, "sample"),
        ({"method": "mean-t", "sample": [1, np.inf], "confidence": 0.95}, "sample"),
        ({"method": "mean-t", "sample": [1, 2], "confidence": True}, "confidence"),
        ({"method": "mean-t", "sample": [1, 2], "confidence": 1}, "confidence"),
        ({"method": "proportion-wilson", "successes": True, "total": 2, "confidence": 0.95}, "successes"),
        ({"method": "proportion-wilson", "successes": 3, "total": 2, "confidence": 0.95}, "successes"),
        ({"method": "proportion-wilson", "successes": 1, "total": 0, "confidence": 0.95}, "total"),
        ({"method": "proportion-wilson", "successes": 1, "total": 2, "confidence": 0.95, "sample": [1, 2]}, "sample"),
        ({"method": "mean-t", "sample": [1, 2], "confidence": 0.95, "total": 2}, "total"),
        ({"method": "mean-t", "sample": [1, 2], "confidence": 0.95, "typo": 1}, "typo"),
    ],
)
def test_confidence_interval_rejects_invalid_or_irrelevant_fields(
    payload: dict[str, object], field: str
) -> None:
    """Accepting invalid confidence/count fields makes a reported interval undefined."""
    with pytest.raises(ValueError, match=field):
        execute("confidence-interval", payload)


def test_statistics_models_are_registered_json_safe_and_do_not_mutate_input() -> None:
    """Undocumented registration, mutation, or non-JSON output breaks safe dispatch."""
    cases = {
        "correlation-analysis": {"x": [1, 2, 3], "y": [2, 4, 6], "method": "pearson"},
        "confidence-interval": {"method": "proportion-wilson", "successes": 1, "total": 4, "confidence": 0.95},
    }
    capabilities = {item["model_id"]: item for item in list_capabilities()}
    for model_id, payload in cases.items():
        before = copy.deepcopy(payload)
        result = execute(model_id, payload)

        assert payload == before
        assert json.loads(json.dumps(result, allow_nan=False)) == result
        assert get_spec(model_id).function is not None
        assert capabilities[model_id]["executor"] == "statistics"
        assert capabilities[model_id]["deterministic"] is True
        assert capabilities[model_id]["seed_supported"] is False
