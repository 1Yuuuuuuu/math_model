from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.executors import optimization
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


def _constant(value: object) -> dict[str, object]:
    return {"op": "constant", "value": value}


def _variable(index: int = 0) -> dict[str, object]:
    return {"op": "variable", "index": index}


def _binary(op: str, left: object, right: object) -> dict[str, object]:
    return {"op": op, "args": [left, right]}


def _square(node: object) -> dict[str, object]:
    return _binary("power", node, _constant(2))


def _nonlinear_payload() -> dict[str, object]:
    return {
        "objective": _square(_binary("subtract", _variable(), _constant(3))),
        "initial": [0],
        "bounds": [[-10, 10]],
        "sense": "minimize",
        "constraints": [],
    }


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


def test_nonlinear_programming_minimizes_quadratic() -> None:
    """Failing to optimize the expression tree leaves the initial point away from x=3."""
    result = execute("nonlinear-programming", _nonlinear_payload())

    assert result["result"]["solution"] == pytest.approx([3], abs=1e-5)
    assert result["result"]["objective"] == pytest.approx(0, abs=1e-10)


def test_nonlinear_programming_supports_equality_and_interval_constraints() -> None:
    """Ignoring either constraint admits a lower but infeasible objective value."""
    objective = _binary("add", _square(_variable(0)), _square(_variable(1)))
    result = execute(
        "nonlinear-programming",
        {
            "objective": objective,
            "initial": [1.4, 1.6],
            "bounds": [[0, 3], [0, 3]],
            "sense": "minimize",
            "constraints": [
                {
                    "type": "equality",
                    "expression": _binary("add", _variable(0), _variable(1)),
                    "target": 3,
                },
                {
                    "type": "interval",
                    "expression": _variable(0),
                    "lower": 1,
                    "upper": 2,
                },
            ],
        },
    )

    assert result["result"]["solution"] == pytest.approx([1.5, 1.5], abs=1e-5)
    assert result["result"]["objective"] == pytest.approx(4.5, abs=1e-8)
    assert result["diagnostics"]["feasibility"]["feasible"] is True
    assert result["diagnostics"]["feasibility"]["max_violation"] <= 1e-8


def test_nonlinear_programming_maximize_restores_objective_sign() -> None:
    """Returning SciPy's internally negated value would report -5 instead of 5."""
    peak = _binary(
        "add",
        {"op": "negate", "args": [_square(_binary("subtract", _variable(), _constant(2)))]},
        _constant(5),
    )
    result = execute(
        "nonlinear-programming",
        {
            "objective": peak,
            "initial": [0],
            "bounds": [[-10, 10]],
            "sense": "maximize",
            "constraints": [],
        },
    )

    assert result["result"]["solution"] == pytest.approx([2], abs=1e-5)
    assert result["result"]["objective"] == pytest.approx(5, abs=1e-9)


@pytest.mark.parametrize(
    ("replacement", "field"),
    [
        ({"objective": "(x - 3) ** 2"}, "objective"),
        ({"objective": lambda values: values[0]}, "objective"),
        ({"initial": []}, "initial"),
        ({"initial": [[0]]}, "initial"),
        ({"initial": [np.nan]}, "initial"),
        ({"initial": [True]}, "initial"),
        ({"bounds": []}, "bounds"),
        ({"bounds": [[0, 1], [0, 1]]}, "bounds"),
        ({"bounds": [[True, 1]]}, "bounds"),
        ({"bounds": [[0, np.inf]]}, "bounds"),
        ({"bounds": [[2, 1]]}, "bounds"),
        ({"sense": "minimum"}, "sense"),
        ({"constraints": {}}, "constraints"),
        ({"constraints": [{"type": "unknown", "expression": _variable()}]}, "constraints"),
        (
            {
                "constraints": [
                    {
                        "type": "equality",
                        "expression": _variable(),
                        "target": 0,
                        "extra": 1,
                    }
                ]
            },
            "constraints",
        ),
        (
            {
                "constraints": [
                    {"type": "equality", "expression": _variable(), "target": True}
                ]
            },
            "constraints",
        ),
        (
            {
                "constraints": [
                    {
                        "type": "interval",
                        "expression": _variable(),
                        "lower": None,
                        "upper": None,
                    }
                ]
            },
            "constraints",
        ),
        (
            {
                "constraints": [
                    {
                        "type": "interval",
                        "expression": _variable(),
                        "lower": 2,
                        "upper": 1,
                    }
                ]
            },
            "constraints",
        ),
        (
            {
                "constraints": [
                    {
                        "type": "interval",
                        "expression": "x",
                        "lower": 0,
                        "upper": 1,
                    }
                ]
            },
            "constraints",
        ),
    ],
)
def test_nonlinear_programming_rejects_malformed_payloads(
    replacement: dict[str, object], field: str
) -> None:
    """Permissive parsing would submit ambiguous or unsafe nonlinear models to SciPy."""
    payload = _nonlinear_payload()
    payload.update(replacement)

    with pytest.raises(ValueError, match=rf"nonlinear-programming: execution stage failed: {field}"):
        execute("nonlinear-programming", payload)


def test_nonlinear_programming_rejects_domain_errors() -> None:
    """A log-domain failure at the initial point must not become a solver result."""
    payload = _nonlinear_payload()
    payload.update(
        {
            "objective": {"op": "log", "args": [_variable()]},
            "initial": [0],
            "bounds": [[0, 1]],
        }
    )

    with pytest.raises(ValueError, match="nonlinear-programming: execution stage failed"):
        execute("nonlinear-programming", payload)


def test_nonlinear_programming_rejects_infeasible_constraints() -> None:
    """Solver failure for an impossible equality must not be surfaced as a solution."""
    payload = _nonlinear_payload()
    payload["bounds"] = [[0, 1]]
    payload["constraints"] = [
        {"type": "equality", "expression": _variable(), "target": 2}
    ]

    with pytest.raises(ValueError, match="nonlinear-programming: execution stage failed: solver"):
        execute("nonlinear-programming", payload)


def test_nonlinear_programming_rejects_nonconverged_solver_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finite iterate is not a solution when SciPy reports non-convergence."""
    monkeypatch.setattr(
        optimization,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(
            success=False,
            status=9,
            message="iteration limit reached",
            x=np.array([2.5]),
            nit=100,
            nfev=200,
        ),
    )

    with pytest.raises(ValueError, match="solver failed.*iteration limit"):
        optimization.execute_nonlinear_programming(_nonlinear_payload())


def test_nonlinear_programming_rechecks_final_feasibility(monkeypatch: pytest.MonkeyPatch) -> None:
    """A solver success flag cannot override a violated final interval constraint."""
    monkeypatch.setattr(
        optimization,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(
            success=True,
            status=0,
            message="claimed success",
            x=np.array([0.0]),
            nit=1,
            nfev=2,
        ),
    )
    payload = _nonlinear_payload()
    payload["constraints"] = [
        {"type": "interval", "expression": _variable(), "lower": 1, "upper": 2}
    ]

    with pytest.raises(ValueError, match="infeasible"):
        optimization.execute_nonlinear_programming(payload)


def test_nonlinear_programming_preserves_input_and_returns_finite_json() -> None:
    """Mutation or NumPy/non-finite output would break repeatability and JSON transport."""
    payload = _nonlinear_payload()
    before = copy.deepcopy(payload)

    result = execute("nonlinear-programming", payload)

    assert payload == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert result["parameters"] == before
    assert result["reproducibility"] == {"seed": None, "deterministic": True}
    assert set(result["diagnostics"]) >= {"status", "message", "nit", "nfev", "feasibility"}


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
        (
            "nonlinear-programming",
            "shared/knowledge/model-cards/optimization/nonlinear-programming.md",
            ("objective", "initial", "bounds", "sense", "constraints"),
        ),
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
