"""Safe expression-tree compilation for numerical model executors."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

import numpy as np

from .base import json_finite_number


_MAX_DEPTH = 16
_MAX_NODES = 256
_UNARY_OPERATIONS = frozenset({"negate", "abs", "exp", "log", "sqrt"})
_BINARY_OPERATIONS = frozenset(
    {"add", "subtract", "multiply", "divide", "power"}
)


def _finite(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("expression produced a non-real result") from exc
    if not math.isfinite(result):
        raise ValueError("expression produced a non-finite result")
    return result


def _runtime_variables(values: object, variable_count: int) -> np.ndarray:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise ValueError("variables must be a finite one-dimensional numeric array")
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as exc:
        raise ValueError("variables must be a finite one-dimensional numeric array") from exc
    if (
        array.ndim != 1
        or array.size != variable_count
        or not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.complexfloating)
        or not np.all(np.isfinite(array))
    ):
        raise ValueError("variables must be a finite one-dimensional numeric array")
    return array.astype(float, copy=False)


def _evaluate(instruction: tuple[object, ...], variables: np.ndarray) -> float:
    op = instruction[0]
    if op == "constant":
        return instruction[1]  # type: ignore[return-value]
    if op == "variable":
        return _finite(variables[instruction[1]])  # type: ignore[index]

    left = _evaluate(instruction[1], variables)  # type: ignore[arg-type]
    try:
        if op == "negate":
            result = -left
        elif op == "abs":
            result = abs(left)
        elif op == "exp":
            result = math.exp(left)
        elif op == "log":
            if left <= 0.0:
                raise ValueError("log is defined only for positive values")
            result = math.log(left)
        elif op == "sqrt":
            if left < 0.0:
                raise ValueError("sqrt is defined only for non-negative values")
            result = math.sqrt(left)
        else:
            right = _evaluate(instruction[2], variables)  # type: ignore[arg-type]
            if op == "add":
                result = left + right
            elif op == "subtract":
                result = left - right
            elif op == "multiply":
                result = left * right
            elif op == "divide":
                if right == 0.0:
                    raise ValueError("division by zero")
                result = left / right
            elif op == "power":
                exponent = instruction[3]
                if left == 0.0 and exponent < 0:  # type: ignore[operator]
                    raise ValueError("zero cannot be raised to a negative power")
                result = left ** exponent  # type: ignore[operator]
            else:  # pragma: no cover - construction admits no other instruction
                raise ValueError("unknown compiled expression operation")
    except (ArithmeticError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("expression arithmetic failed") from exc
    return _finite(result)


def compile_expression(
    node: object, *, variable_count: int
) -> Callable[[np.ndarray], float]:
    """Validate and compile a bounded expression tree into a numerical callable."""
    if type(variable_count) is not int or variable_count < 0:
        raise ValueError("variable_count must be a non-negative integer")
    count = variable_count
    nodes_seen = 0
    active: set[int] = set()

    def build(current: object, depth: int) -> tuple[object, ...]:
        nonlocal nodes_seen
        if depth > _MAX_DEPTH:
            raise ValueError(f"expression depth exceeds {_MAX_DEPTH}")
        nodes_seen += 1
        if nodes_seen > _MAX_NODES:
            raise ValueError(f"expression node count exceeds {_MAX_NODES}")
        if type(current) is not dict:
            raise ValueError("each expression node must be a plain JSON object")
        keys = dict.keys(current)
        if any(type(key) is not str for key in keys):
            raise ValueError("expression node keys must be strings")
        identity = id(current)
        if identity in active:
            raise ValueError("expression tree contains a cyclic reference")
        active.add(identity)
        try:
            op = dict.get(current, "op")
            if type(op) is not str:
                raise ValueError("expression node op must be a string")
            if op == "constant":
                if set(dict.keys(current)) != {"op", "value"}:
                    raise ValueError("constant node must contain exactly op and value")
                finite_value = json_finite_number(
                    dict.__getitem__(current, "value"), "constant value"
                )
                assert finite_value is not None
                return (op, finite_value)
            if op == "variable":
                if set(dict.keys(current)) != {"op", "index"}:
                    raise ValueError("variable node must contain exactly op and index")
                index = dict.__getitem__(current, "index")
                if type(index) is not int or not 0 <= index < count:
                    raise ValueError("variable index is outside the declared range")
                return (op, index)
            if op not in _UNARY_OPERATIONS and op not in _BINARY_OPERATIONS:
                raise ValueError(f"unknown expression operation: {op}")
            if set(dict.keys(current)) != {"op", "args"}:
                raise ValueError(f"{op} node must contain exactly op and args")
            args = dict.__getitem__(current, "args")
            arity = 1 if op in _UNARY_OPERATIONS else 2
            if type(args) is not list or len(args) != arity:
                raise ValueError(f"{op} operation requires exactly {arity} argument(s)")
            if op == "power":
                exponent_node = args[1]
                if (
                    type(exponent_node) is not dict
                    or any(type(key) is not str for key in dict.keys(exponent_node))
                    or set(dict.keys(exponent_node)) != {"op", "value"}
                    or type(dict.get(exponent_node, "op")) is not str
                    or dict.get(exponent_node, "op") != "constant"
                ):
                    raise ValueError("power exponent must be a constant integer from -8 to 8")
                exponent = dict.__getitem__(exponent_node, "value")
                if type(exponent) is not int or not -8 <= exponent <= 8:
                    raise ValueError("power exponent must be a constant integer from -8 to 8")
            compiled = tuple(build(child, depth + 1) for child in args)
            if op == "power":
                return (op, compiled[0], compiled[1], exponent)
            return (op, *compiled)
        finally:
            active.remove(identity)

    instruction = build(node, 1)

    def evaluate(values: np.ndarray) -> float:
        variables = _runtime_variables(values, count)
        return _finite(_evaluate(instruction, variables))

    return evaluate
