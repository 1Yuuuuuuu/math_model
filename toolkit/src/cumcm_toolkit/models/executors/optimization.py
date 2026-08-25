"""Deterministic linear and mixed-integer programming executors."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Integral, Real

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from .base import numeric_array, required_mapping, string_enum


_SENSES = frozenset({"minimize", "maximize"})
_INTEGRALITY_CODES = frozenset({0, 1, 2, 3})


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
            if endpoint is None:
                endpoints.append(None)
            elif isinstance(endpoint, (bool, np.bool_)) or not isinstance(endpoint, Real):
                raise ValueError("bounds: endpoints must be finite numbers or null")
            else:
                number = float(endpoint)
                if not math.isfinite(number):
                    raise ValueError("bounds: endpoints must be finite numbers or null")
                endpoints.append(number)
        if endpoints[0] is not None and endpoints[1] is not None and endpoints[0] > endpoints[1]:
            raise ValueError("bounds: lower endpoint must not exceed upper endpoint")
        lower[index] = -np.inf if endpoints[0] is None else endpoints[0]
        upper[index] = np.inf if endpoints[1] is None else endpoints[1]
        normalized.append(endpoints)
    return lower, upper, normalized


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


def _raw_result(
    *,
    objective: np.ndarray,
    sense: str,
    bounds: list[list[float | None]],
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
    }
    warnings: list[str] = []
    if mip_result is not None:
        for attribute, name in (("mip_dual_bound", "mip_dual_bound"), ("mip_gap", "mip_gap")):
            value = getattr(mip_result, attribute, None)
            if isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value)):
                diagnostics[name] = float(value)
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
        solution=solution,
        objective_value=objective_value,
        inequality=inequality,
        equality=equality,
        status=result.status,
        message=result.message,
        integrality=integrality,
        mip_result=result,
    )
