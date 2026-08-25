"""Safe expression-tree compilation for numerical model executors."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from numbers import Integral, Real

import numpy as np


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
    if (
        isinstance(variable_count, (bool, np.bool_))
        or not isinstance(variable_count, Integral)
        or variable_count < 0
    ):
        raise ValueError("variable_count must be a non-negative integer")
    count = int(variable_count)
    nodes_seen = 0
    active: set[int] = set()

    def build(current: object, depth: int) -> tuple[object, ...]:
        nonlocal nodes_seen
        if depth > _MAX_DEPTH:
            raise ValueError(f"expression depth exceeds {_MAX_DEPTH}")
        nodes_seen += 1
        if nodes_seen > _MAX_NODES:
            raise ValueError(f"expression node count exceeds {_MAX_NODES}")
        if not isinstance(current, Mapping):
            raise ValueError("each expression node must be a mapping")
        if any(not isinstance(key, str) for key in current):
            raise ValueError("expression node keys must be strings")
        identity = id(current)
        if identity in active:
            raise ValueError("expression tree contains a cyclic reference")
        active.add(identity)
        try:
            op = current.get("op")
            if not isinstance(op, str):
                raise ValueError("expression node op must be a string")
            if op == "constant":
                if set(current) != {"op", "value"}:
                    raise ValueError("constant node must contain exactly op and value")
                value = current["value"]
                if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
                    raise ValueError("constant value must be a finite number")
                try:
                    finite_value = _finite(value)
                except ValueError as exc:
                    raise ValueError("constant value must be a finite number") from exc
                return (op, finite_value)
            if op == "variable":
                if set(current) != {"op", "index"}:
                    raise ValueError("variable node must contain exactly op and index")
                index = current["index"]
                if (
                    isinstance(index, (bool, np.bool_))
                    or not isinstance(index, Integral)
                    or not 0 <= index < count
                ):
                    raise ValueError("variable index is outside the declared range")
                return (op, int(index))
            if op not in _UNARY_OPERATIONS and op not in _BINARY_OPERATIONS:
                raise ValueError(f"unknown expression operation: {op}")
            if set(current) != {"op", "args"}:
                raise ValueError(f"{op} node must contain exactly op and args")
            args = current["args"]
            arity = 1 if op in _UNARY_OPERATIONS else 2
            if not isinstance(args, (list, tuple)) or len(args) != arity:
                raise ValueError(f"{op} operation requires exactly {arity} argument(s)")
            if op == "power":
                exponent_node = args[1]
                if (
                    not isinstance(exponent_node, Mapping)
                    or set(exponent_node) != {"op", "value"}
                    or exponent_node.get("op") != "constant"
                ):
                    raise ValueError("power exponent must be a constant integer from -8 to 8")
                exponent = exponent_node["value"]
                if (
                    isinstance(exponent, (bool, np.bool_))
                    or not isinstance(exponent, Integral)
                    or not -8 <= exponent <= 8
                ):
                    raise ValueError("power exponent must be a constant integer from -8 to 8")
            compiled = tuple(build(child, depth + 1) for child in args)
            if op == "power":
                return (op, compiled[0], compiled[1], int(exponent))
            return (op, *compiled)
        finally:
            active.remove(identity)

    instruction = build(node, 1)

    def evaluate(values: np.ndarray) -> float:
        variables = _runtime_variables(values, count)
        return _finite(_evaluate(instruction, variables))

    return evaluate
