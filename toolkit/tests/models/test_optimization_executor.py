from __future__ import annotations

import json

import numpy as np
import pytest

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


def test_linear_programming_known_optimum() -> None:
    """Neglecting the maximize conversion would choose the wrong feasible vertex."""
    result = execute(
        "linear-programming",
        {
            "objective": [3, 2],
            "sense": "maximize",
            "bounds": [[0, None], [0, None]],
            "inequality": {
                "matrix": [[1, 1], [1, 0], [0, 1]],
                "upper": [4, 2, 3],
            },
        },
    )

    assert result["result"]["solution"] == pytest.approx([2, 2])
    assert result["result"]["objective"] == pytest.approx(10)
    solution = np.asarray(result["result"]["solution"])
    assert np.all(np.asarray([[1, 1], [1, 0], [0, 1]]) @ solution <= [4, 2, 3])


def test_linear_programming_minimizes_with_equality_and_unbounded_endpoints() -> None:
    """Omitting equality constraints or treating JSON null as a numeric bound changes this optimum."""
    result = execute(
        "linear-programming",
        {
            "objective": [1, 2],
            "sense": "minimize",
            "bounds": [[None, None], [0, None]],
            "equality": {"matrix": [[1, 1]], "target": [3]},
            "inequality": {"matrix": [[1, 0]], "upper": [2]},
        },
    )

    assert result["result"]["solution"] == pytest.approx([2, 1])
    assert result["result"]["objective"] == pytest.approx(4)
    assert result["diagnostics"]["equality_residuals"] == pytest.approx([0])
    assert result["diagnostics"]["inequality_residuals"] == pytest.approx([0])


def test_integer_programming_does_not_round_continuous_solution() -> None:
    """Rounding an LP relaxation would return 3, outside the declared upper bound of 2.7."""
    result = execute(
        "integer-programming",
        {
            "objective": [1],
            "sense": "maximize",
            "bounds": [[0, 2.7]],
            "integrality": [1],
        },
    )

    assert result["result"]["solution"] == pytest.approx([2])
    assert result["result"]["objective"] == pytest.approx(2)


def test_integer_programming_maximize_restores_the_mip_dual_bound_sign() -> None:
    """Leaking the internally negated objective makes a maximum bound of 9 appear as -9."""
    result = execute(
        "integer-programming",
        {
            "objective": [9],
            "sense": "maximize",
            "bounds": [[0, 1]],
            "integrality": [1],
        },
    )

    assert result["result"]["objective"] == pytest.approx(9)
    assert result["diagnostics"]["mip_dual_bound"] == pytest.approx(9)


@pytest.mark.parametrize("model_id", ["linear-programming", "integer-programming"])
def test_optimization_models_report_calculated_feasibility_summary(model_id: str) -> None:
    """Hard-coding solver success as feasibility would hide violations in the returned solution."""
    payload: dict[str, object] = {
        "objective": [1, 2],
        "sense": "minimize",
        "bounds": [[None, 2], [0, None]],
        "equality": {"matrix": [[1, 1]], "target": [3]},
        "inequality": {"matrix": [[1, 0]], "upper": [2]},
    }
    if model_id == "integer-programming":
        payload["integrality"] = [1, 1]

    result = execute(model_id, payload)

    assert result["diagnostics"]["feasibility"] == {
        "tolerance": 1e-8,
        "feasible": True,
        "max_bound_violation": 0.0,
        "max_inequality_violation": 0.0,
        "max_equality_violation": 0.0,
        "max_violation": 0.0,
    }


@pytest.mark.parametrize(
    ("model_id", "payload", "field"),
    [
        ("linear-programming", {"objective": [1], "sense": "maximize", "bounds": [[0, 1], [0, 1]]}, "bounds"),
        ("linear-programming", {"objective": [1], "sense": "maximize", "bounds": [[2, 1]]}, "bounds"),
        ("linear-programming", {"objective": [True], "sense": "maximize", "bounds": [[0, 1]]}, "objective"),
        ("linear-programming", {"objective": [np.inf], "sense": "maximize", "bounds": [[0, 1]]}, "objective"),
        ("linear-programming", {"objective": [1], "sense": "maximum", "bounds": [[0, 1]]}, "sense"),
        ("linear-programming", {"objective": [1, 1], "sense": "maximize", "bounds": [[0, 1], [0, 1]], "inequality": {"matrix": [[1], [1]], "upper": [1, 1]}}, "inequality"),
        ("linear-programming", {"objective": [1, 1], "sense": "maximize", "bounds": [[0, 1], [0, 1]], "equality": {"matrix": [[1, 1]], "target": [1, 1]}}, "equality"),
        ("linear-programming", {"objective": [1, 1], "sense": "maximize", "bounds": [[0, 1], [0, 1]], "inequality": {"matrix": [[1, 1], [1]], "upper": [1, 1]}}, "inequality"),
        ("integer-programming", {"objective": [1], "sense": "maximize", "bounds": [[0, 1]], "integrality": [True]}, "integrality"),
        ("integer-programming", {"objective": [1], "sense": "maximize", "bounds": [[0, 1]], "integrality": [1.0]}, "integrality"),
        ("integer-programming", {"objective": [1], "sense": "maximize", "bounds": [[0, 1]], "integrality": [4]}, "integrality"),
    ],
)
def test_optimization_models_reject_invalid_input_shapes_and_values(
    model_id: str, payload: dict[str, object], field: str
) -> None:
    """Relaxing these payload checks would submit malformed models to SciPy."""
    with pytest.raises(ValueError, match=rf"{model_id}: execution stage failed: {field}"):
        execute(model_id, payload)


@pytest.mark.parametrize(
    "model_id",
    ["linear-programming", "integer-programming"],
)
def test_optimization_models_report_infeasible_models(model_id: str) -> None:
    """Treating a solver failure as a result would expose a non-solution to callers."""
    payload: dict[str, object] = {
        "objective": [1],
        "sense": "minimize",
        "bounds": [[0, 1]],
        "inequality": {"matrix": [[1]], "upper": [-1]},
    }
    if model_id == "integer-programming":
        payload["integrality"] = [1]

    with pytest.raises(ValueError, match=rf"{model_id}: execution stage failed: solver"):
        execute(model_id, payload)


@pytest.mark.parametrize(
    "model_id",
    ["linear-programming", "integer-programming"],
)
def test_optimization_models_report_unbounded_models(model_id: str) -> None:
    """A non-success solver status must not be surfaced as an optimal objective."""
    payload: dict[str, object] = {
        "objective": [-1],
        "sense": "minimize",
        "bounds": [[None, None]],
    }
    if model_id == "integer-programming":
        payload["integrality"] = [1]

    with pytest.raises(ValueError, match=rf"{model_id}: execution stage failed: solver"):
        execute(model_id, payload)


@pytest.mark.parametrize("model_id", ["linear-programming", "integer-programming"])
def test_optimization_results_are_finite_json_round_trippable(model_id: str) -> None:
    """NumPy values or nonfinite diagnostics would violate the public result contract."""
    payload: dict[str, object] = {
        "objective": [1, 1],
        "sense": "maximize",
        "bounds": [[0, 1], [0, 1]],
        "inequality": {"matrix": [[1, 1]], "upper": [1]},
    }
    if model_id == "integer-programming":
        payload["integrality"] = [1, 1]

    result = execute(model_id, payload)

    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert result["parameters"]["sense"] == "maximize"
    assert result["input_summary"]["variables"] == 2
    assert result["reproducibility"] == {"seed": None, "deterministic": True}


def test_optimization_specifications_are_registered_with_documented_contracts() -> None:
    """An executor that is not registered with its card cannot be dispatched safely."""
    capabilities = {item["model_id"]: item for item in list_capabilities()}

    for model_id, card, fields in (
        ("linear-programming", "shared/knowledge/model-cards/optimization/linear-programming.md", ("objective", "sense", "bounds")),
        ("integer-programming", "shared/knowledge/model-cards/optimization/integer-programming.md", ("objective", "sense", "bounds", "integrality")),
    ):
        assert get_spec(model_id).function is not None
        assert capabilities[model_id] == {
            "model_id": model_id,
            "executor": "optimization",
            "knowledge_card": card,
            "deterministic": True,
            "seed_supported": False,
            "payload_fields": fields,
        }
