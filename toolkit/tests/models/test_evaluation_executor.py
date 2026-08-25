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

    for model_id, card in (
        ("topsis", "shared/knowledge/model-cards/evaluation/topsis.md"),
        ("entropy-weight", "shared/knowledge/model-cards/evaluation/entropy-weight.md"),
    ):
        assert get_spec(model_id).function is not None
        assert capabilities[model_id] == {
            "model_id": model_id,
            "executor": "evaluation",
            "knowledge_card": card,
            "deterministic": True,
            "seed_supported": False,
            "payload_fields": ("matrix", "criteria"),
        }
