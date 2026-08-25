"""Deterministic linear, mixed-integer, and nonlinear programming executors."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from numbers import Integral, Real

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, NonlinearConstraint, linprog, milp, minimize

from .base import json_finite_number, numeric_array, required_mapping, string_enum
from .expression import compile_expression


_SENSES = frozenset({"minimize", "maximize"})
_INTEGRALITY_CODES = frozenset({0, 1, 2, 3})
_FEASIBILITY_TOLERANCE = 1e-8


NonlinearExpressionConstraint = tuple[
    str, Callable[[np.ndarray], float], float, float
]


def _objective(payload: Mapping[str, object]) -> np.ndarray:
    return numeric_array(payload, "objective", ndim=1).astype(float, copy=False)


def _bounds(payload: Mapping[str, object], variables: int) -> tuple[np.ndarray, np.ndarray, list[list[float | None]]]:
    value = payload.get("bounds")
    if not isinstance(value, (list, tuple)) or len(value) != variables:
        raise ValueError("bounds: length must match the number of objective coefficients")

    lower = np.empty(variables, dtype=float)
    upper = np.empty(variables, dtype=float)
    normalized: list[list[float | None]] = []
    for index, pair in enumerate(value):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("bounds: each bound must be a [lower, upper] pair")
        endpoints: list[float | None] = []
        for endpoint in pair:
            endpoints.append(
                json_finite_number(endpoint, "bounds: endpoints", allow_none=True)
            )
        if endpoints[0] is not None and endpoints[1] is not None and endpoints[0] > endpoints[1]:
            raise ValueError("bounds: lower endpoint must not exceed upper endpoint")
        lower[index] = -np.inf if endpoints[0] is None else endpoints[0]
        upper[index] = np.inf if endpoints[1] is None else endpoints[1]
        normalized.append(endpoints)
    return lower, upper, normalized


def _constraint_endpoint(value: object, *, field: str, allow_none: bool) -> float | None:
    return json_finite_number(value, field, allow_none=allow_none)


def _nonlinear_constraints(
    payload: Mapping[str, object], variables: int
) -> tuple[list[NonlinearExpressionConstraint], list[dict[str, object]]]:
    value = payload.get("constraints")
    if type(value) is not list:
        raise ValueError("constraints: must be a plain JSON array")
    compiled: list[NonlinearExpressionConstraint] = []
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(value):
        field = f"constraints[{index}]"
        if type(item) is not dict or any(
            type(key) is not str for key in dict.keys(item)
        ):
            raise ValueError(f"{field}: must be a plain JSON object with string keys")
        kind = dict.get(item, "type")
        if type(kind) is not str:
            raise ValueError(f"{field}: type must be equality or interval")
        if kind == "equality":
            if set(dict.keys(item)) != {"type", "expression", "target"}:
                raise ValueError(
                    f"{field}: equality must contain exactly type, expression, and target"
                )
            target = _constraint_endpoint(
                dict.__getitem__(item, "target"),
                field=f"{field}.target",
                allow_none=False,
            )
            assert target is not None
            lower = upper = target
            normalized_item = {
                "type": "equality",
                "expression": dict.__getitem__(item, "expression"),
                "target": target,
            }
        elif kind == "interval":
            if set(dict.keys(item)) != {"type", "expression", "lower", "upper"}:
                raise ValueError(
                    f"{field}: interval must contain exactly type, expression, lower, and upper"
                )
            lower_value = _constraint_endpoint(
                dict.__getitem__(item, "lower"),
                field=f"{field}.lower",
                allow_none=True,
            )
            upper_value = _constraint_endpoint(
                dict.__getitem__(item, "upper"),
                field=f"{field}.upper",
                allow_none=True,
            )
            if lower_value is None and upper_value is None:
                raise ValueError(f"{field}: interval must have at least one finite endpoint")
            if (
                lower_value is not None
                and upper_value is not None
                and lower_value > upper_value
            ):
                raise ValueError(f"{field}: lower endpoint must not exceed upper endpoint")
            lower = -math.inf if lower_value is None else lower_value
            upper = math.inf if upper_value is None else upper_value
            normalized_item = {
                "type": "interval",
                "expression": dict.__getitem__(item, "expression"),
                "lower": lower_value,
                "upper": upper_value,
            }
        else:
            raise ValueError(f"{field}: type must be equality or interval")
        try:
            function = compile_expression(
                dict.__getitem__(item, "expression"), variable_count=variables
            )
        except ValueError as exc:
            raise ValueError(f"{field}.expression: {exc}") from exc
        compiled.append((kind, function, lower, upper))
        normalized.append(normalized_item)
    return compiled, normalized


def _constraint(
    payload: Mapping[str, object], field: str, rhs_field: str, variables: int
) -> tuple[np.ndarray, np.ndarray] | None:
    if field not in payload:
        return None
    value = required_mapping(payload, field)
    try:
        matrix_value = value["matrix"]
        rhs_value = value[rhs_field]
    except KeyError as exc:
        raise ValueError(f"{field}: must contain matrix and {rhs_field}") from exc
    try:
        matrix = numeric_array({"matrix": matrix_value}, "matrix", ndim=2).astype(
            float, copy=False
        )
        rhs = numeric_array({rhs_field: rhs_value}, rhs_field, ndim=1).astype(
            float, copy=False
        )
    except ValueError as exc:
        raise ValueError(f"{field}: invalid matrix or {rhs_field}") from exc
    if matrix.shape[1] != variables:
        raise ValueError(f"{field}: matrix columns must match the number of objective coefficients")
    if rhs.size != matrix.shape[0]:
        raise ValueError(f"{field}: {rhs_field} length must match the number of matrix rows")
    return matrix, rhs


def _integrality(payload: Mapping[str, object], variables: int) -> np.ndarray:
    value = payload.get("integrality")
    if not isinstance(value, (list, tuple)) or len(value) != variables:
        raise ValueError("integrality: length must match the number of objective coefficients")
    codes: list[int] = []
    for code in value:
        if isinstance(code, (bool, np.bool_)) or not isinstance(code, Integral):
            raise ValueError("integrality: each value must be an integer from 0 to 3")
        integer_code = int(code)
        if integer_code not in _INTEGRALITY_CODES:
            raise ValueError("integrality: each value must be an integer from 0 to 3")
        codes.append(integer_code)
    return np.asarray(codes, dtype=int)


def _validated_problem(payload: Mapping[str, object]) -> tuple[
    np.ndarray, str, np.ndarray, np.ndarray, list[list[float | None]], tuple[np.ndarray, np.ndarray] | None, tuple[np.ndarray, np.ndarray] | None
]:
    objective = _objective(payload)
    sense = string_enum(payload, "sense", _SENSES)
    lower, upper, normalized_bounds = _bounds(payload, objective.size)
    inequality = _constraint(payload, "inequality", "upper", objective.size)
    equality = _constraint(payload, "equality", "target", objective.size)
    return objective, sense, lower, upper, normalized_bounds, inequality, equality


def _checked_solution(solution: object, objective: np.ndarray) -> tuple[np.ndarray, float]:
    values = np.asarray(solution, dtype=float)
    if values.shape != objective.shape or not np.all(np.isfinite(values)):
        raise ValueError("solver returned a non-finite solution")
    value = float(np.dot(objective, values))
    if not math.isfinite(value):
        raise ValueError("solver returned a non-finite objective")
    return values, value


def _residuals(
    solution: np.ndarray,
    inequality: tuple[np.ndarray, np.ndarray] | None,
    equality: tuple[np.ndarray, np.ndarray] | None,
) -> dict[str, list[float]]:
    diagnostics: dict[str, list[float]] = {}
    if inequality is not None:
        matrix, upper = inequality
        residual = upper - matrix @ solution
        if not np.all(np.isfinite(residual)):
            raise ValueError("solver returned non-finite inequality residuals")
        diagnostics["inequality_residuals"] = residual.tolist()
    if equality is not None:
        matrix, target = equality
        residual = matrix @ solution - target
        if not np.all(np.isfinite(residual)):
            raise ValueError("solver returned non-finite equality residuals")
        diagnostics["equality_residuals"] = residual.tolist()
    return diagnostics


def _feasibility_summary(
    solution: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    inequality: tuple[np.ndarray, np.ndarray] | None,
    equality: tuple[np.ndarray, np.ndarray] | None,
) -> dict[str, float | bool]:
    """Calculate finite primal violations from the returned solution, not solver status."""
    max_bound_violation = float(
        max(
            np.maximum(lower - solution, 0.0).max(initial=0.0),
            np.maximum(solution - upper, 0.0).max(initial=0.0),
        )
    )
    max_inequality_violation = 0.0
    if inequality is not None:
        matrix, upper_rhs = inequality
        max_inequality_violation = float(
            np.maximum(matrix @ solution - upper_rhs, 0.0).max(initial=0.0)
        )
    max_equality_violation = 0.0
    if equality is not None:
        matrix, target = equality
        max_equality_violation = float(np.abs(matrix @ solution - target).max(initial=0.0))
    max_violation = float(
        max(max_bound_violation, max_inequality_violation, max_equality_violation)
    )
    if not math.isfinite(max_violation):
        raise ValueError("solver returned non-finite feasibility violations")
    return {
        "tolerance": _FEASIBILITY_TOLERANCE,
        "feasible": max_violation <= _FEASIBILITY_TOLERANCE,
        "max_bound_violation": max_bound_violation,
        "max_inequality_violation": max_inequality_violation,
        "max_equality_violation": max_equality_violation,
        "max_violation": max_violation,
    }


def _raw_result(
    *,
    objective: np.ndarray,
    sense: str,
    bounds: list[list[float | None]],
    lower: np.ndarray,
    upper: np.ndarray,
    solution: np.ndarray,
    objective_value: float,
    inequality: tuple[np.ndarray, np.ndarray] | None,
    equality: tuple[np.ndarray, np.ndarray] | None,
    status: object,
    message: object,
    integrality: np.ndarray | None = None,
    mip_result: object | None = None,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "solver_status": int(status),
        "solver_message": str(message),
        **_residuals(solution, inequality, equality),
        "feasibility": _feasibility_summary(solution, lower, upper, inequality, equality),
    }
    warnings: list[str] = []
    if mip_result is not None:
        for attribute, name in (("mip_dual_bound", "mip_dual_bound"), ("mip_gap", "mip_gap")):
            value = getattr(mip_result, attribute, None)
            if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value)):
                diagnostics[name] = -float(value) if name == "mip_dual_bound" and sense == "maximize" else float(value)
            else:
                warnings.append(f"MILP solver did not report a finite {name}")
    parameters: dict[str, object] = {
        "objective": objective.tolist(),
        "sense": sense,
        "bounds": bounds,
    }
    if inequality is not None:
        parameters["inequality"] = {"matrix": inequality[0].tolist(), "upper": inequality[1].tolist()}
    if equality is not None:
        parameters["equality"] = {"matrix": equality[0].tolist(), "target": equality[1].tolist()}
    if integrality is not None:
        parameters["integrality"] = integrality.tolist()
    return {
        "parameters": parameters,
        "input_summary": {
            "variables": objective.size,
            "inequality_constraints": 0 if inequality is None else inequality[0].shape[0],
            "equality_constraints": 0 if equality is None else equality[0].shape[0],
        },
        "result": {"solution": solution.tolist(), "objective": objective_value},
        "diagnostics": diagnostics,
        "warnings": warnings,
        "seed": None,
    }


def execute_linear_programming(payload: Mapping[str, object]) -> dict[str, object]:
    """Solve a bounded-or-explicitly-unbounded continuous linear program with HiGHS."""
    objective, sense, lower, upper, normalized_bounds, inequality, equality = _validated_problem(payload)
    solver_objective = -objective if sense == "maximize" else objective
    result = linprog(
        solver_objective,
        A_ub=None if inequality is None else inequality[0],
        b_ub=None if inequality is None else inequality[1],
        A_eq=None if equality is None else equality[0],
        b_eq=None if equality is None else equality[1],
        bounds=list(zip(lower, upper, strict=True)),
        method="highs",
    )
    if not result.success:
        raise ValueError(f"solver failed (status {result.status}): {result.message}")
    solution, objective_value = _checked_solution(result.x, objective)
    return _raw_result(
        objective=objective,
        sense=sense,
        bounds=normalized_bounds,
        lower=lower,
        upper=upper,
        solution=solution,
        objective_value=objective_value,
        inequality=inequality,
        equality=equality,
        status=result.status,
        message=result.message,
    )


def execute_integer_programming(payload: Mapping[str, object]) -> dict[str, object]:
    """Solve a mixed-integer linear program with SciPy's HiGHS-backed ``milp`` adapter."""
    objective, sense, lower, upper, normalized_bounds, inequality, equality = _validated_problem(payload)
    integrality = _integrality(payload, objective.size)
    solver_objective = -objective if sense == "maximize" else objective
    constraints: list[LinearConstraint] = []
    if inequality is not None:
        matrix, upper_rhs = inequality
        constraints.append(LinearConstraint(matrix, -np.inf, upper_rhs))
    if equality is not None:
        matrix, target = equality
        constraints.append(LinearConstraint(matrix, target, target))
    result = milp(
        c=solver_objective,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=constraints or None,
    )
    if not result.success:
        raise ValueError(f"solver failed (status {result.status}): {result.message}")
    solution, objective_value = _checked_solution(result.x, objective)
    return _raw_result(
        objective=objective,
        sense=sense,
        bounds=normalized_bounds,
        lower=lower,
        upper=upper,
        solution=solution,
        objective_value=objective_value,
        inequality=inequality,
        equality=equality,
        status=result.status,
        message=result.message,
        integrality=integrality,
        mip_result=result,
    )


def _nonlinear_feasibility_summary(
    solution: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    constraints: list[NonlinearExpressionConstraint],
) -> tuple[dict[str, float | bool], list[float]]:
    max_bound_violation = float(
        max(
            np.maximum(lower - solution, 0.0).max(initial=0.0),
            np.maximum(solution - upper, 0.0).max(initial=0.0),
        )
    )
    max_inequality_violation = 0.0
    max_equality_violation = 0.0
    constraint_values: list[float] = []
    for kind, function, constraint_lower, constraint_upper in constraints:
        value = function(solution)
        constraint_values.append(value)
        if kind == "equality":
            max_equality_violation = max(
                max_equality_violation, abs(value - constraint_lower)
            )
        else:
            max_inequality_violation = max(
                max_inequality_violation,
                max(constraint_lower - value, 0.0),
                max(value - constraint_upper, 0.0),
            )
    max_violation = float(
        max(max_bound_violation, max_inequality_violation, max_equality_violation)
    )
    if not math.isfinite(max_violation):
        raise ValueError("solver returned non-finite feasibility violations")
    return (
        {
            "tolerance": _FEASIBILITY_TOLERANCE,
            "feasible": max_violation <= _FEASIBILITY_TOLERANCE,
            "max_bound_violation": max_bound_violation,
            "max_inequality_violation": max_inequality_violation,
            "max_equality_violation": max_equality_violation,
            "max_violation": max_violation,
        },
        constraint_values,
    )


def _solver_integer(
    result: object, attribute: str, *, missing_default: int | None = None
) -> int:
    if not hasattr(result, attribute):
        if missing_default is not None:
            return missing_default
        raise ValueError(f"solver returned an invalid {attribute}")
    value = getattr(result, attribute)
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"solver returned an invalid {attribute}")
    number = int(value)
    if number < 0:
        raise ValueError(f"solver returned an invalid {attribute}")
    return number


def execute_nonlinear_programming(payload: Mapping[str, object]) -> dict[str, object]:
    """Solve a bounded nonlinear program from validated expression trees using SLSQP."""
    initial = numeric_array(payload, "initial", ndim=1).astype(float, copy=False)
    variables = initial.size
    lower, upper, normalized_bounds = _bounds(payload, variables)
    sense = string_enum(payload, "sense", _SENSES)
    try:
        objective_node = payload["objective"]
    except KeyError as exc:
        raise ValueError("objective: field is required") from exc
    try:
        objective = compile_expression(objective_node, variable_count=variables)
    except ValueError as exc:
        raise ValueError(f"objective: {exc}") from exc
    constraints, normalized_constraints = _nonlinear_constraints(payload, variables)

    solver_constraints = [
        NonlinearConstraint(function, constraint_lower, constraint_upper)
        for _, function, constraint_lower, constraint_upper in constraints
    ]

    def solver_objective(values: np.ndarray) -> float:
        value = objective(values)
        return -value if sense == "maximize" else value

    result = minimize(
        solver_objective,
        initial,
        method="SLSQP",
        bounds=Bounds(lower, upper),
        constraints=solver_constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not bool(getattr(result, "success", False)):
        raise ValueError(
            f"solver failed (status {getattr(result, 'status', 'unknown')}): "
            f"{getattr(result, 'message', 'unknown failure')}"
        )

    solution = np.asarray(getattr(result, "x", None), dtype=float)
    if solution.shape != initial.shape or not np.all(np.isfinite(solution)):
        raise ValueError("solver returned a non-finite solution")
    objective_value = objective(solution)
    feasibility, constraint_values = _nonlinear_feasibility_summary(
        solution, lower, upper, constraints
    )
    if not feasibility["feasible"]:
        raise ValueError(
            f"solver returned an infeasible solution (maximum violation "
            f"{feasibility['max_violation']})"
        )

    diagnostics: dict[str, object] = {
        "status": _solver_integer(result, "status", missing_default=0),
        "message": str(getattr(result, "message", "")),
        "nit": _solver_integer(result, "nit", missing_default=0),
        "nfev": _solver_integer(result, "nfev", missing_default=0),
        "constraint_values": constraint_values,
        "feasibility": feasibility,
    }
    if hasattr(result, "njev"):
        diagnostics["njev"] = _solver_integer(result, "njev")
    return {
        "parameters": {
            "objective": objective_node,
            "initial": initial.tolist(),
            "bounds": normalized_bounds,
            "sense": sense,
            "constraints": normalized_constraints,
        },
        "input_summary": {
            "variables": variables,
            "constraints": len(constraints),
            "equality_constraints": sum(
                kind == "equality" for kind, *_ in constraints
            ),
            "interval_constraints": sum(
                kind == "interval" for kind, *_ in constraints
            ),
        },
        "result": {"solution": solution.tolist(), "objective": objective_value},
        "diagnostics": diagnostics,
        "warnings": [],
        "seed": None,
    }
