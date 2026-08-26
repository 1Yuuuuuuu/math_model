"""Public behavior tests for correlation and confidence-interval execution."""

from __future__ import annotations

import copy
import json
import math

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
    p_value = result["result"]["p_value"]
    sample_size = np.asarray(result["result"]["sample_size"])
    assert coefficient.shape == sample_size.shape == (3, 3)
    np.testing.assert_allclose(coefficient, coefficient.T)
    assert np.array_equal(sample_size, sample_size.T)
    assert np.all(np.diag(coefficient) == 1.0)
    assert all(p_value[index][index] is None for index in range(3))
    assert all(
        p_value[left][right] == pytest.approx(p_value[right][left])
        for left in range(3)
        for right in range(3)
        if left != right
    )
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


def test_matrix_diagonal_is_exact_but_has_no_p_value_hypothesis() -> None:
    """A diagonal p-value would incorrectly present a self-correlation as a tested pair."""
    result = execute(
        "correlation-analysis",
        {"matrix": [[1, 2], [2, 4], [3, 9]], "method": "kendall"},
    )

    assert result["result"]["coefficient"][0][0] == 1.0
    assert result["result"]["p_value"][0][0] is None
    assert "not applicable" in result["diagnostics"]["diagonal"]


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


def test_mean_t_uses_stable_tail_probability_at_maximum_finite_confidence() -> None:
    """A rounded upper quantile would reject an otherwise valid confidence level below one."""
    confidence = math.nextafter(1.0, 0.0)
    result = execute(
        "confidence-interval", {"method": "mean-t", "sample": [1, 2], "confidence": confidence}
    )

    assert math.isfinite(result["result"]["lower"])
    assert math.isfinite(result["result"]["upper"])
    assert result["result"]["lower"] < result["result"]["estimate"] < result["result"]["upper"]


def test_mean_t_keeps_nonzero_subnormal_variance_when_standard_error_underflows() -> None:
    """Dividing a positive subnormal scale before applying t must not mark variance as zero."""
    smallest = float.fromhex("0x0.0000000000001p-1022")
    result = execute(
        "confidence-interval",
        {"method": "mean-t", "sample": [0.0, smallest, smallest, smallest], "confidence": 0.95},
    )

    assert result["diagnostics"]["zero_variance"] is False
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


def test_wilson_uses_stable_tail_at_maximum_finite_confidence() -> None:
    """A rounded upper quantile would reject an otherwise valid confidence level below one."""
    confidence = math.nextafter(1.0, 0.0)
    near_one = execute(
        "confidence-interval",
        {"method": "proportion-wilson", "successes": 1, "total": 10, "confidence": confidence},
    )

    assert math.isfinite(near_one["result"]["lower"])
    assert math.isfinite(near_one["result"]["upper"])


def test_wilson_large_total_keeps_a_nonzero_interval() -> None:
    """Overflow in an intermediate denominator must not collapse a nonzero Wilson interval."""
    huge_total = execute(
        "confidence-interval",
        {"method": "proportion-wilson", "successes": 1, "total": 10**308, "confidence": 0.95},
    )

    assert huge_total["result"]["lower"] < huge_total["result"]["estimate"] < huge_total["result"]["upper"]


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


@pytest.mark.parametrize(
    ("test_name", "payload", "scipy_call"),
    [
        (
            "one-sample-t",
            {"sample": [2, 3, 5, 8], "population_mean": 1},
            lambda: stats.ttest_1samp([2, 3, 5, 8], 1, alternative="two-sided"),
        ),
        (
            "independent-t",
            {"sample_a": [1, 2, 4], "sample_b": [5, 8, 9], "equal_variance": False},
            lambda: stats.ttest_ind(
                [1, 2, 4], [5, 8, 9], equal_var=False, alternative="two-sided"
            ),
        ),
        (
            "paired-t",
            {"sample_a": [1, 2, 5, 7], "sample_b": [0, 2, 3, 4]},
            lambda: stats.ttest_rel([1, 2, 5, 7], [0, 2, 3, 4], alternative="two-sided"),
        ),
    ],
)
def test_parametric_methods_match_scipy_and_report_complete_summary(
    test_name: str, payload: dict[str, object], scipy_call: object
) -> None:
    """Using the wrong SciPy routine changes the statistic and degrees of freedom."""
    result = execute("parametric-test", {"test": test_name, **payload})
    expected = scipy_call()

    assert result["result"]["statistic"] == pytest.approx(expected.statistic)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)
    assert math.isfinite(result["result"]["effect_size"])
    assert math.isfinite(result["result"]["degrees_freedom"])
    assert "mean_difference" in result["result"]
    assert result["parameters"]["alternative"] == "two-sided"


@pytest.mark.parametrize("alternative", ["two-sided", "less", "greater"])
def test_parametric_alternative_is_forwarded_to_scipy(alternative: str) -> None:
    """Ignoring a one-sided alternative can reverse the inferential result."""
    result = execute(
        "parametric-test",
        {
            "test": "one-sample-t",
            "sample": [3, 4, 5, 8],
            "population_mean": 1,
            "alternative": alternative,
        },
    )
    expected = stats.ttest_1samp([3, 4, 5, 8], 1, alternative=alternative)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)


def test_independent_t_explicitly_selects_equal_variance_formula() -> None:
    """Silently forcing Welch changes the requested equal-variance degrees of freedom."""
    result = execute(
        "parametric-test",
        {
            "test": "independent-t",
            "sample_a": [1, 2, 3],
            "sample_b": [4, 8, 12, 16],
            "equal_variance": True,
        },
    )
    assert result["result"]["degrees_freedom"] == 5
    assert result["parameters"]["equal_variance"] is True
    assert result["input_summary"] == {"sample_size_a": 3, "sample_size_b": 4}


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"test": "one-sample-t", "sample": [1], "population_mean": 0}, "sample"),
        ({"test": "one-sample-t", "sample": [1, 2], "population_mean": True}, "population_mean"),
        (
            {
                "test": "independent-t",
                "sample_a": [1],
                "sample_b": [2, 3],
                "equal_variance": False,
            },
            "sample_a",
        ),
        (
            {"test": "independent-t", "sample_a": [1, 2], "sample_b": [3, 4], "equal_variance": 1},
            "equal_variance",
        ),
        ({"test": "paired-t", "sample_a": [1, 2], "sample_b": [1]}, "equal lengths"),
        ({"test": "paired-t", "sample_a": [1, 2], "sample_b": [1, math.inf]}, "sample_b"),
        (
            {"test": "one-sample-t", "sample": [1, 2], "population_mean": 0, "alternative": "up"},
            "alternative",
        ),
        ({"test": "not-a-test", "sample": [1, 2], "population_mean": 0}, "test"),
        ({"test": "one-sample-t", "sample": [1, 2], "population_mean": 0, "typo": 1}, "typo"),
    ],
)
def test_parametric_test_rejects_invalid_or_irrelevant_inputs(
    payload: dict[str, object], field: str
) -> None:
    """Permitting malformed samples or irrelevant fields makes the selected t-test ambiguous."""
    with pytest.raises(ValueError, match=field):
        execute("parametric-test", payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"test": "one-sample-t", "sample": [1, 1, 1], "population_mean": 0},
        {
            "test": "independent-t",
            "sample_a": [1, 1],
            "sample_b": [2, 2],
            "equal_variance": False,
        },
        {"test": "paired-t", "sample_a": [2, 3], "sample_b": [1, 2]},
    ],
)
def test_parametric_test_fails_closed_when_statistic_or_effect_is_undefined(
    payload: dict[str, object],
) -> None:
    """Zero effect denominators and numerical overflow must not leak NaN or infinity."""
    with pytest.raises(ValueError, match="finite|variance|effect|defined"):
        execute("parametric-test", payload)


def test_one_sample_t_keeps_large_finite_values_json_safe() -> None:
    """Large representable samples must remain finite, never leak non-JSON floats."""
    result = execute(
        "parametric-test",
        {"test": "one-sample-t", "sample": [1e308, -1e308], "population_mean": 0},
    )
    assert all(
        math.isfinite(result["result"][field])
        for field in ("statistic", "p_value", "effect_size", "degrees_freedom", "mean_difference")
    )


@pytest.mark.parametrize(
    ("test_name", "payload", "scipy_call"),
    [
        (
            "mann-whitney-u",
            {"sample_a": [1, 2, 3], "sample_b": [4, 6, 8]},
            lambda: stats.mannwhitneyu([1, 2, 3], [4, 6, 8], alternative="two-sided"),
        ),
        (
            "wilcoxon",
            {"sample_a": [1, 2, 5, 8], "sample_b": [0, 2, 3, 4]},
            lambda: stats.wilcoxon([1, 2, 5, 8], [0, 2, 3, 4], alternative="two-sided"),
        ),
        (
            "kruskal-wallis",
            {"groups": [[1, 2], [3, 5], [8, 13]]},
            lambda: stats.kruskal([1, 2], [3, 5], [8, 13]),
        ),
    ],
)
def test_rank_methods_match_scipy_and_return_finite_effect_size(
    test_name: str, payload: dict[str, object], scipy_call: object
) -> None:
    """Using the wrong rank test changes the tested sampling design."""
    result = execute("nonparametric-test", {"test": test_name, **payload})
    expected = scipy_call()

    assert result["result"]["statistic"] == pytest.approx(expected.statistic)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)
    assert math.isfinite(result["result"]["effect_size"])


@pytest.mark.parametrize("alternative", ["two-sided", "less", "greater"])
def test_two_sample_rank_alternative_is_forwarded(alternative: str) -> None:
    """Dropping the requested direction silently changes a one-sided rank test."""
    result = execute(
        "nonparametric-test",
        {
            "test": "mann-whitney-u",
            "sample_a": [1, 2, 3],
            "sample_b": [3, 4, 5],
            "alternative": alternative,
        },
    )
    expected = stats.mannwhitneyu([1, 2, 3], [3, 4, 5], alternative=alternative)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)


def test_chi_square_returns_expected_counts_and_low_frequency_warning() -> None:
    """A sparse table must preserve expected counts and an applicability warning."""
    table = [[1, 0], [0, 1]]
    result = execute("nonparametric-test", {"test": "chi-square", "table": table})
    expected = stats.chi2_contingency(table)

    assert result["result"]["statistic"] == pytest.approx(expected.statistic)
    assert result["result"]["p_value"] == pytest.approx(expected.pvalue)
    np.testing.assert_allclose(result["result"]["expected_counts"], expected.expected_freq)
    assert any("below 5" in warning for warning in result["warnings"])
    assert math.isfinite(result["result"]["effect_size"])


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"test": "mann-whitney-u", "sample_a": [], "sample_b": [1]}, "sample_a"),
        (
            {
                "test": "mann-whitney-u",
                "sample_a": [1],
                "sample_b": [2],
                "alternative": "up",
            },
            "alternative",
        ),
        ({"test": "wilcoxon", "sample_a": [1, 2], "sample_b": [1]}, "equal lengths"),
        ({"test": "wilcoxon", "sample_a": [1, 2], "sample_b": [1, np.nan]}, "sample_b"),
        ({"test": "kruskal-wallis", "groups": [[1, 2]]}, "groups"),
        ({"test": "kruskal-wallis", "groups": [[1], []]}, "groups"),
        ({"test": "kruskal-wallis", "groups": {(1, 2), (3, 4)}}, "groups"),
        ({"test": "chi-square", "table": [[1, 2, 3]]}, "table"),
        ({"test": "chi-square", "table": [[1, -1], [2, 3]]}, "table"),
        ({"test": "chi-square", "table": [[True, False], [False, True]]}, "table"),
        ({"test": "chi-square", "table": [[0, 0], [1, 2]]}, "table"),
        ({"test": "chi-square", "table": [[1, 2], [3, 4]], "alternative": "less"}, "alternative"),
        ({"test": "kruskal-wallis", "groups": [[1, 2], [3, 4]], "typo": 1}, "typo"),
    ],
)
def test_nonparametric_test_rejects_invalid_or_irrelevant_inputs(
    payload: dict[str, object], field: str
) -> None:
    """Accepting malformed designs or method-specific fields changes the intended rank test."""
    with pytest.raises(ValueError, match=field):
        execute("nonparametric-test", payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"test": "wilcoxon", "sample_a": [1, 2, 3], "sample_b": [1, 2, 3]},
        {"test": "kruskal-wallis", "groups": [[1], [1]]},
        {"test": "kruskal-wallis", "groups": [[1], [2]]},
    ],
)
def test_rank_tests_fail_closed_for_degenerate_statistics_or_effects(
    payload: dict[str, object],
) -> None:
    """All-zero differences and undefined effect denominators must never become NaN output."""
    with pytest.raises(ValueError, match="defined|finite|differences|samples"):
        execute("nonparametric-test", payload)


def test_hypothesis_test_models_are_registered_json_safe_and_do_not_mutate_input() -> None:
    """Missing registration, mutation, or non-JSON output breaks the public execution contract."""
    cases = {
        "parametric-test": {
            "test": "independent-t",
            "sample_a": [1, 2, 4],
            "sample_b": [5, 7, 9],
            "equal_variance": False,
        },
        "nonparametric-test": {
            "test": "chi-square",
            "table": [[10, 20], [20, 10]],
        },
    }
    capabilities = {item["model_id"]: item for item in list_capabilities()}
    for model_id, payload in cases.items():
        before = copy.deepcopy(payload)
        result = execute(model_id, payload)

        assert payload == before
        assert json.loads(json.dumps(result, allow_nan=False)) == result
        assert capabilities[model_id]["knowledge_card"] == (
            "shared/knowledge/model-cards/statistics/parametric-tests.md"
            if model_id == "parametric-test"
            else "shared/knowledge/model-cards/statistics/nonparametric-tests.md"
        )
        assert capabilities[model_id]["deterministic"] is True
        assert capabilities[model_id]["seed_supported"] is False


@pytest.mark.parametrize(
    ("model_id", "payload", "field"),
    [
        (
            "parametric-test",
            {"test": "one-sample-t", "sample": [1, True, 2], "population_mean": 0},
            "sample",
        ),
        (
            "parametric-test",
            {"test": "independent-t", "sample_a": [1, 2], "sample_b": [3, False]},
            "sample_b",
        ),
        (
            "parametric-test",
            {"test": "paired-t", "sample_a": [1, True], "sample_b": [0, 2]},
            "sample_a",
        ),
        (
            "nonparametric-test",
            {"test": "mann-whitney-u", "sample_a": [1, True], "sample_b": [2, 3]},
            "sample_a",
        ),
        (
            "nonparametric-test",
            {"test": "wilcoxon", "sample_a": [1, 2], "sample_b": [0, False]},
            "sample_b",
        ),
        (
            "nonparametric-test",
            {"test": "kruskal-wallis", "groups": [[1, True], [2, 3]]},
            "groups",
        ),
        (
            "nonparametric-test",
            {"test": "chi-square", "table": [[1, True], [2, 3]]},
            "table",
        ),
    ],
)
def test_hypothesis_tests_reject_boolean_leaves_before_numpy_coercion(
    model_id: str, payload: dict[str, object], field: str
) -> None:
    """A mixed bool/numeric list must not be coerced to an integer array."""
    with pytest.raises(ValueError, match=field):
        execute(model_id, payload)


def test_hypothesis_tests_reject_numeric_subclasses_without_invoking_hooks() -> None:
    """Only plain JSON int/float leaves are valid; subclass conversion hooks are unsafe."""

    class HookedInt(int):
        def __float__(self) -> float:
            raise AssertionError("numeric subclass conversion hook was invoked")

    with pytest.raises(ValueError, match="sample"):
        execute(
            "parametric-test",
            {"test": "one-sample-t", "sample": [1, HookedInt(2), 3], "population_mean": 0},
        )


@pytest.mark.parametrize(
    ("payload", "scaled_payload"),
    [
        (
            {"test": "one-sample-t", "sample": [0.0, 1.0], "population_mean": 0.25},
            {
                "test": "one-sample-t",
                "sample": [0.0, 1e-200],
                "population_mean": 2.5e-201,
            },
        ),
        (
            {
                "test": "independent-t",
                "sample_a": [0.0, 1.0, 3.0],
                "sample_b": [2.0, 4.0, 7.0],
                "equal_variance": False,
            },
            {
                "test": "independent-t",
                "sample_a": [0.0, 1e-200, 3e-200],
                "sample_b": [2e-200, 4e-200, 7e-200],
                "equal_variance": False,
            },
        ),
        (
            {"test": "paired-t", "sample_a": [1.0, 3.0, 6.0, 10.0], "sample_b": [0.0, 1.0, 3.0, 6.0]},
            {
                "test": "paired-t",
                "sample_a": [1e-200, 3e-200, 6e-200, 1e-199],
                "sample_b": [0.0, 1e-200, 3e-200, 6e-200],
            },
        ),
    ],
)
def test_t_tests_are_invariant_under_common_positive_subnormal_scale(
    payload: dict[str, object], scaled_payload: dict[str, object]
) -> None:
    """Underflow in SciPy's raw variance must not change scale-free inference."""
    baseline = execute("parametric-test", payload)["result"]
    scaled = execute("parametric-test", scaled_payload)["result"]

    for field in ("statistic", "p_value", "effect_size", "degrees_freedom"):
        assert scaled[field] == pytest.approx(baseline[field])


def test_one_sample_t_preserves_smallest_subnormal_mean() -> None:
    """Dividing each subnormal observation by n before summing erases its mean."""
    smallest = math.ulp(0.0)
    baseline = execute(
        "parametric-test",
        {"test": "one-sample-t", "sample": [1.0, 1.0, 1.0, 2.0], "population_mean": 0.0},
    )["result"]
    scaled = execute(
        "parametric-test",
        {
            "test": "one-sample-t",
            "sample": [smallest, smallest, smallest, 2.0 * smallest],
            "population_mean": 0.0,
        },
    )["result"]

    assert scaled["mean_difference"] == smallest
    for field in ("statistic", "p_value", "effect_size", "degrees_freedom"):
        assert scaled[field] == pytest.approx(baseline[field])
