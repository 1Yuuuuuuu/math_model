from __future__ import annotations

import json

import numpy as np
import pytest

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


def test_topsis_known_two_alternative_order() -> None:
    """Swapping benefit and cost ideals would reverse this hand-checked order."""
    result = execute(
        "topsis",
        {
            "matrix": [[90, 10], [70, 30]],
            "criteria": ["benefit", "cost"],
            "weights": [0.5, 0.5],
        },
    )

    assert result["result"]["ranking"] == [0, 1]
    assert result["result"]["closeness"] == pytest.approx([1.0, 0.0])


def test_topsis_uses_equal_weights_when_weights_are_omitted() -> None:
    """Removing the optional-weight default would make a valid evaluation fail."""
    result = execute(
        "topsis",
        {"matrix": [[4, 1], [1, 4]], "criteria": ["benefit", "cost"]},
    )

    assert result["parameters"]["weights"] == pytest.approx([0.5, 0.5])
    assert result["result"]["ranking"] == [0, 1]


@pytest.mark.parametrize(
    "weights",
    [
        [-0.1, 1.1],
        [0.5, 0.49],
        [0.5],
        [float("nan"), 1.0],
    ],
)
def test_topsis_rejects_invalid_weights(weights: list[float]) -> None:
    """Relaxing weight sign, sum, length, or finiteness checks must fail closed."""
    with pytest.raises(ValueError, match="weights"):
        execute(
            "topsis",
            {"matrix": [[1, 2], [3, 4]], "criteria": ["benefit", "cost"], "weights": weights},
        )


@pytest.mark.parametrize(
    "criteria",
    [["benefit"], ["benefit", "neutral"], "benefit,cost"],
)
def test_topsis_rejects_invalid_criteria(criteria: object) -> None:
    """Misaligned or unsupported criterion directions cannot yield an interpretable ranking."""
    with pytest.raises(ValueError, match="criteria"):
        execute("topsis", {"matrix": [[1, 2], [3, 4]], "criteria": criteria})


@pytest.mark.parametrize(
    "matrix",
    [
        [[0, 1], [0, 2]],
        [[5, 1], [5, 2]],
        [[1, 1], [1, 1]],
    ],
)
def test_topsis_rejects_undefined_ideal_distances(matrix: list[list[float]]) -> None:
    """Zero-norm columns and coincident ideals have no defined TOPSIS closeness."""
    with pytest.raises(ValueError):
        execute("topsis", {"matrix": matrix, "criteria": ["benefit", "cost"]})


def test_entropy_weight_prefers_varying_column() -> None:
    """Treating a constant column as informative would give it nonzero weight."""
    result = execute(
        "entropy-weight",
        {"matrix": [[1, 5], [2, 5], [4, 5]], "criteria": ["benefit", "benefit"]},
    )

    assert result["result"]["weights"] == pytest.approx([1.0, 0.0])
    assert result["result"]["ranking"] == [2, 1, 0]
    assert "zero information" in " ".join(result["warnings"])


def test_entropy_weight_orients_cost_criteria_before_ranking() -> None:
    """Dropping cost orientation would rank the expensive alternative ahead of the cheap one."""
    result = execute(
        "entropy-weight",
        {"matrix": [[8, 10], [4, 40]], "criteria": ["benefit", "cost"]},
    )

    assert result["result"]["ranking"] == [0, 1]


def test_entropy_weight_deduplicates_constant_column_warning() -> None:
    """Multiple constant columns should not repeat the same user-facing warning."""
    result = execute(
        "entropy-weight",
        {"matrix": [[1, 5, 8], [2, 5, 8], [4, 5, 8]], "criteria": ["benefit"] * 3},
    )

    assert result["warnings"] == ["one or more criteria have zero information and weight 0"]
    assert result["result"]["weights"] == pytest.approx([1.0, 0.0, 0.0])


def test_entropy_weight_rejects_all_zero_information() -> None:
    """Normalizing zero divergence would otherwise return undefined entropy weights."""
    with pytest.raises(ValueError, match="zero information"):
        execute(
            "entropy-weight",
            {"matrix": [[5, 1], [5, 1]], "criteria": ["benefit", "cost"]},
        )


@pytest.mark.parametrize(
    "model_id",
    ["topsis", "entropy-weight"],
)
@pytest.mark.parametrize(
    "matrix",
    [
        [[1, 2], [3]],
        [[1, np.inf], [2, 3]],
        [1, 2, 3],
    ],
)
def test_evaluation_models_reject_malformed_or_nonfinite_matrices(
    model_id: str, matrix: object
) -> None:
    """Bypassing shared numeric validation would admit malformed evaluation inputs."""
    with pytest.raises(ValueError, match="matrix"):
        execute(model_id, {"matrix": matrix, "criteria": ["benefit", "cost"]})


@pytest.mark.parametrize("model_id", ["topsis", "entropy-weight"])
def test_evaluation_results_are_finite_json_round_trippable(model_id: str) -> None:
    """Returning NumPy scalars or nonfinite values would break the public result contract."""
    result = execute(
        model_id,
        {"matrix": [[1, 8], [2, 4], [4, 1]], "criteria": ["benefit", "cost"]},
    )

    serialized = json.dumps(result, allow_nan=False)
    assert json.loads(serialized) == result


def test_evaluation_specifications_are_registered_with_documented_contracts() -> None:
    """Unregistered models cannot be dispatched, even when their executors exist."""
    capabilities = {item["model_id"]: item for item in list_capabilities()}

    for model_id, card, payload_fields in (
        ("topsis", "shared/knowledge/model-cards/evaluation/topsis.md", ("matrix", "criteria")),
        (
            "entropy-weight",
            "shared/knowledge/model-cards/evaluation/entropy-weight.md",
            ("matrix", "criteria"),
        ),
        ("ahp", "shared/knowledge/model-cards/evaluation/ahp.md", ("pairwise_matrix",)),
        (
            "grey-relational-analysis",
            "shared/knowledge/model-cards/evaluation/grey-relational.md",
            ("reference", "comparatives"),
        ),
    ):
        assert get_spec(model_id).function is not None
        assert capabilities[model_id] == {
            "model_id": model_id,
            "executor": "evaluation",
            "knowledge_card": card,
            "deterministic": True,
            "seed_supported": False,
            "payload_fields": payload_fields,
        }


def test_ahp_consistent_matrix_returns_expected_weights() -> None:
    """Choosing a non-principal eigenvector would change these hand-checked weights."""
    result = execute(
        "ahp",
        {"pairwise_matrix": [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]},
    )

    assert result["result"]["weights"] == pytest.approx([4 / 7, 2 / 7, 1 / 7], abs=1e-6)
    assert result["result"]["lambda_max"] == pytest.approx(3.0)
    assert result["result"]["CI"] == pytest.approx(0.0)
    assert result["result"]["CR"] == pytest.approx(0.0)
    assert result["diagnostics"]["consistent"] is True


def test_ahp_reports_inconsistent_judgements_without_failing() -> None:
    """Rejecting an inconsistent but valid matrix would hide the consistency diagnosis."""
    result = execute(
        "ahp",
        {"pairwise_matrix": [[1, 9, 1 / 9], [1 / 9, 1, 9], [9, 1 / 9, 1]]},
    )

    assert result["result"]["CR"] > 0.1
    assert result["diagnostics"]["consistent"] is False


@pytest.mark.parametrize("size", [1, 2])
def test_ahp_small_matrices_skip_consistency_ratio(size: int) -> None:
    """Dividing by RI for one or two criteria would fabricate a consistency ratio."""
    matrix = [[1.0]] if size == 1 else [[1.0, 3.0], [1 / 3, 1.0]]

    result = execute("ahp", {"pairwise_matrix": matrix})

    assert result["result"]["CR"] is None
    assert "not required" in result["diagnostics"]["consistency_note"]


def test_ahp_stably_solves_a_consistent_high_dynamic_range_matrix() -> None:
    """Ordinary floating-point eigendecomposition loses the tiny positive principal weights."""
    result = execute(
        "ahp",
        {
            "pairwise_matrix": [
                [1, 1e-150, 1e-300],
                [1e150, 1, 1e-150],
                [1e300, 1e150, 1],
            ]
        },
    )

    weights = result["result"]["weights"]
    assert np.log10(weights[0]) == pytest.approx(-300, abs=1e-6)
    assert np.log10(weights[1]) == pytest.approx(-150, abs=1e-6)
    assert weights[2] == pytest.approx(1.0)
    assert result["result"]["lambda_max"] == pytest.approx(3.0)
    assert result["diagnostics"]["consistent"] is True


def test_ahp_uses_the_ri_value_at_the_upper_supported_size() -> None:
    """An off-by-one RI lookup would make the size-15 consistency result incorrect."""
    result = execute("ahp", {"pairwise_matrix": [[1.0] * 15 for _ in range(15)]})

    assert result["result"]["CI"] == pytest.approx(0.0)
    assert result["result"]["CR"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "matrix",
    [
        [[1, 2], [0.4, 1]],
        [[1, 0], [1, 1]],
        [[1, 2, 3], [0.5, 1, 2]],
        [[1] * 16 for _ in range(16)],
        [[1, np.inf], [0, 1]],
    ],
)
def test_ahp_rejects_invalid_pairwise_matrices(matrix: object) -> None:
    """Admitting non-reciprocal, nonpositive, malformed, oversized, or nonfinite matrices is invalid."""
    with pytest.raises(ValueError, match="ahp: execution stage failed: pairwise_matrix"):
        execute("ahp", {"pairwise_matrix": matrix})


def test_grey_relational_identical_series_ranks_first() -> None:
    """Losing the all-zero-difference branch would turn an identical series into NaN."""
    result = execute(
        "grey-relational-analysis",
        {"reference": [1, 2, 3], "comparatives": [[1, 2, 3], [3, 2, 1]], "rho": 0.5},
    )

    assert result["result"]["coefficients"][0] == pytest.approx([1.0, 1.0, 1.0])
    assert result["result"]["grades"][0] == pytest.approx(1.0)
    assert result["result"]["ranking"][0] == 0


def test_grey_relational_all_identical_series_have_unit_coefficients() -> None:
    """An all-zero delta maximum must produce finite unit coefficients for every series."""
    result = execute(
        "grey-relational-analysis",
        {"reference": [2, 4, 6], "comparatives": [[2, 4, 6], [2, 4, 6]]},
    )

    assert result["result"]["coefficients"] == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
    assert result["result"]["grades"] == [1.0, 1.0]
    assert result["result"]["ranking"] == [0, 1]


def test_grey_relational_mean_normalization_is_stable_at_large_finite_scale() -> None:
    """Overflowing a finite mean to infinity must not silently normalize the sequence to zero."""
    result = execute(
        "grey-relational-analysis",
        {
            "reference": [1e308, 1e308],
            "comparatives": [[1e308, 1e308]],
            "normalization": "mean",
        },
    )

    assert result["diagnostics"]["normalized_reference"] == pytest.approx([1.0, 1.0])
    assert result["diagnostics"]["normalized_comparatives"][0] == pytest.approx([1.0, 1.0])


def test_grey_relational_mean_normalization_rejects_an_all_zero_sequence() -> None:
    """A zero scale still represents a zero mean and must not first create NaN values."""
    with pytest.raises(ValueError, match="mean normalization requires nonzero sequence mean"):
        execute(
            "grey-relational-analysis",
            {
                "reference": [0, 0],
                "comparatives": [[1, 2]],
                "normalization": "mean",
            },
        )


def test_grey_relational_keeps_the_smallest_positive_rho_finite() -> None:
    """Multiplying rho by delta_max must not underflow and create a 0/0 coefficient."""
    rho = float(np.nextafter(0.0, 1.0))
    result = execute(
        "grey-relational-analysis",
        {"reference": [2, 3], "comparatives": [[2, 2]], "rho": rho},
    )

    assert result["result"]["coefficients"][0][0] == pytest.approx(1.0)
    assert result["result"]["coefficients"][0][1] == rho
    assert result["result"]["grades"][0] == pytest.approx(0.5)


@pytest.mark.parametrize("normalization", ["mean", "range"])
def test_grey_relational_accepts_each_noninitial_normalization(normalization: str) -> None:
    """Rejecting a documented normalization mode would unnecessarily narrow the public contract."""
    result = execute(
        "grey-relational-analysis",
        {
            "reference": [1, 2, 3],
            "comparatives": [[2, 4, 6]],
            "normalization": normalization,
        },
    )

    assert result["result"]["grades"] == pytest.approx([1.0])


def test_grey_relational_uses_the_nontrivial_coefficient_formula() -> None:
    """Replacing the denominator with only the difference changes this hand-derived grade."""
    result = execute(
        "grey-relational-analysis",
        {"reference": [2, 3], "comparatives": [[2, 2]], "rho": 0.5},
    )

    assert result["result"]["coefficients"][0] == pytest.approx([1.0, 1 / 3])
    assert result["result"]["grades"] == pytest.approx([2 / 3])


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"reference": [1, 2], "comparatives": [[1, 2]], "rho": 0}, "rho"),
        ({"reference": [1, 2], "comparatives": [[1, 2]], "rho": 1.1}, "rho"),
        ({"reference": [1, 2], "comparatives": [[1, 2]], "normalization": "zscore"}, "normalization"),
        ({"reference": [1, 2], "comparatives": [[1, 2, 3]]}, "comparatives"),
        ({"reference": [0, 2], "comparatives": [[1, 2]], "normalization": "initial"}, "reference"),
        ({"reference": [1, 2], "comparatives": [[0, 2]], "normalization": "initial"}, "comparatives"),
        ({"reference": [1, -1], "comparatives": [[1, 2]], "normalization": "mean"}, "reference"),
        ({"reference": [1, 2], "comparatives": [[2, -2]], "normalization": "mean"}, "comparatives"),
        ({"reference": [1, 1], "comparatives": [[1, 2]], "normalization": "range"}, "reference"),
        ({"reference": [1, 2], "comparatives": [[3, 3]], "normalization": "range"}, "comparatives"),
        ({"reference": [1, np.nan], "comparatives": [[1, 2]]}, "reference"),
    ],
)
def test_grey_relational_rejects_invalid_inputs(payload: dict[str, object], field: str) -> None:
    """Invalid coefficients, shapes, normalization divisors, or nonfinite values cannot be ranked."""
    with pytest.raises(ValueError, match=rf"grey-relational-analysis: execution stage failed: {field}"):
        execute("grey-relational-analysis", payload)


@pytest.mark.parametrize("model_id", ["ahp", "grey-relational-analysis"])
def test_new_evaluation_results_are_finite_json_round_trippable(model_id: str) -> None:
    """Non-JSON values in either new evaluation result must be rejected at the public boundary."""
    payload = (
        {"pairwise_matrix": [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]}
        if model_id == "ahp"
        else {"reference": [1, 2, 3], "comparatives": [[1, 2, 3], [3, 2, 1]]}
    )

    result = execute(model_id, payload)

    serialized = json.dumps(result, allow_nan=False)
    assert json.loads(serialized) == result
