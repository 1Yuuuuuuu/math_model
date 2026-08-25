from __future__ import annotations

import math

import numpy as np
import pytest

from cumcm_toolkit.models.executors.expression import compile_expression


def _constant(value: object) -> dict[str, object]:
    return {"op": "constant", "value": value}


def _variable(index: object = 0) -> dict[str, object]:
    return {"op": "variable", "index": index}


def _unary(op: str, child: object) -> dict[str, object]:
    return {"op": op, "args": [child]}


def _binary(op: str, left: object, right: object) -> dict[str, object]:
    return {"op": op, "args": [left, right]}


def _balanced_add_tree(leaf: dict[str, object], leaves: int) -> dict[str, object]:
    nodes = [leaf] * leaves
    while len(nodes) > 1:
        next_level: list[dict[str, object]] = []
        for index in range(0, len(nodes) - 1, 2):
            next_level.append(_binary("add", nodes[index], nodes[index + 1]))
        if len(nodes) % 2:
            next_level.append(nodes[-1])
        nodes = next_level
    return nodes[0]


def test_expression_tree_evaluates_quadratic() -> None:
    """Replacing the integer-power implementation with another operator changes 3^2."""
    fn = compile_expression(
        _binary("power", _variable(), _constant(2)), variable_count=1
    )

    assert fn(np.array([3.0])) == pytest.approx(9.0)


@pytest.mark.parametrize(
    ("node", "values", "expected"),
    [
        (_constant(2), [4.0], 2.0),
        (_variable(), [4.0], 4.0),
        (_binary("add", _variable(), _constant(2)), [4.0], 6.0),
        (_binary("subtract", _variable(), _constant(2)), [4.0], 2.0),
        (_binary("multiply", _variable(), _constant(2)), [4.0], 8.0),
        (_binary("divide", _variable(), _constant(2)), [4.0], 2.0),
        (_binary("power", _variable(), _constant(2)), [4.0], 16.0),
        (_unary("negate", _variable()), [4.0], -4.0),
        (_unary("abs", _variable()), [-4.0], 4.0),
        (_unary("exp", _variable()), [1.0], math.e),
        (_unary("log", _variable()), [math.e], 1.0),
        (_unary("sqrt", _variable()), [4.0], 2.0),
    ],
)
def test_expression_tree_supports_each_approved_operation(
    node: dict[str, object], values: list[float], expected: float
) -> None:
    """Dropping or misrouting any documented operation changes its hand-checked value."""
    fn = compile_expression(node, variable_count=1)

    assert fn(np.asarray(values)) == pytest.approx(expected)


@pytest.mark.parametrize(
    "node",
    [
        {"op": "python", "code": "import os"},
        {"op": "constant", "value": 1, "extra": 2},
        {"op": "variable", "index": 0, "args": []},
        {"op": "negate", "args": []},
        {"op": "negate", "args": [_constant(1), _constant(2)]},
        {"op": "add", "args": [_constant(1)]},
        {"op": "add", "args": [_constant(1), _constant(2), _constant(3)]},
        {"op": "add", "args": [_constant(1), 2]},
        {"op": "constant"},
        {"op": "variable"},
        {"args": [_constant(1)]},
        1,
    ],
)
def test_expression_tree_rejects_unknown_fields_wrong_arity_and_bare_numbers(
    node: object,
) -> None:
    """Permissive node parsing would admit undocumented syntax or ambiguous bare literals."""
    with pytest.raises(ValueError):
        compile_expression(node, variable_count=1)


def test_expression_tree_rejects_dict_subclasses_before_mapping_hooks() -> None:
    """A dict subclass must not present inconsistent keys and operation values."""
    calls: list[str] = []

    class InconsistentDict(dict[str, object]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            calls.append("__iter__")
            return super().__iter__()

        def get(self, key: str, default: object = None) -> object:
            calls.append("get")
            return "constant" if key == "op" else super().get(key, default)

    node = InconsistentDict({"op": "python", "value": 1})

    with pytest.raises(ValueError):
        compile_expression(node, variable_count=0)
    assert calls == []


def test_expression_tree_rejects_list_subclasses_before_sequence_hooks() -> None:
    """A list subclass must not spoof arity and later expose fewer children."""
    calls: list[str] = []

    class InconsistentList(list[object]):
        def __len__(self) -> int:
            calls.append("__len__")
            return 2

    node = _binary("add", _constant(1), _constant(2))
    node["args"] = InconsistentList([_constant(1)])

    with pytest.raises(ValueError):
        compile_expression(node, variable_count=0)
    assert calls == []


@pytest.mark.parametrize("index", [True, 0.0, -1, 1])
def test_expression_tree_rejects_invalid_variable_indexes(index: object) -> None:
    """Coercing indexes would allow booleans, fractions, or out-of-range variables."""
    with pytest.raises(ValueError, match="index"):
        compile_expression(_variable(index), variable_count=1)


@pytest.mark.parametrize("location", ["index", "exponent"])
def test_expression_tree_rejects_integer_subclasses_before_conversion_hooks(
    location: str,
) -> None:
    """An integer subclass must not rewrite a validated index or exponent via __int__."""
    calls: list[str] = []

    class RewritingInteger(int):
        def __int__(self) -> int:
            calls.append("__int__")
            return 99

    value = RewritingInteger(0)
    node = (
        _variable(value)
        if location == "index"
        else _binary("power", _constant(2), _constant(value))
    )
    with pytest.raises(ValueError):
        compile_expression(node, variable_count=1)
    assert calls == []


@pytest.mark.parametrize("value", [True, np.nan, np.inf, -np.inf, "1"])
def test_expression_tree_rejects_invalid_constants(value: object) -> None:
    """Non-real or non-finite constants can leak invalid values into the solver."""
    with pytest.raises(ValueError, match="constant"):
        compile_expression(_constant(value), variable_count=1)


def test_expression_tree_rejects_float_subclasses_before_conversion_hooks() -> None:
    """A float subclass must not replace its validated constant through __float__."""
    calls: list[str] = []

    class RewritingFloat(float):
        def __float__(self) -> float:
            calls.append("__float__")
            return 99.0

    with pytest.raises(ValueError):
        compile_expression(_constant(RewritingFloat(2.0)), variable_count=0)
    assert calls == []


@pytest.mark.parametrize("exponent", [-9, 9, 2.0, True])
def test_expression_tree_rejects_invalid_power_exponents(exponent: object) -> None:
    """Relaxing the bounded-integer exponent contract expands the unsafe numeric surface."""
    with pytest.raises(ValueError, match="power"):
        compile_expression(
            _binary("power", _variable(), _constant(exponent)), variable_count=1
        )


def test_expression_tree_rejects_nonconstant_power_exponent() -> None:
    """Variable exponents violate the deliberately bounded power operation."""
    with pytest.raises(ValueError, match="power"):
        compile_expression(
            _binary("power", _variable(), _variable()), variable_count=1
        )


@pytest.mark.parametrize("exponent", [-8, 0, 8])
def test_expression_tree_accepts_power_exponent_boundaries(exponent: int) -> None:
    """Off-by-one checks must not reject either documented exponent boundary."""
    fn = compile_expression(
        _binary("power", _constant(2), _constant(exponent)), variable_count=0
    )

    assert fn(np.array([])) == pytest.approx(2.0**exponent)


def test_expression_tree_enforces_depth_limit() -> None:
    """A depth check applied after recursion would still permit an over-deep tree."""
    depth_sixteen: dict[str, object] = _constant(1)
    for _ in range(15):
        depth_sixteen = _unary("negate", depth_sixteen)
    assert compile_expression(depth_sixteen, variable_count=0)(np.array([])) == -1.0

    depth_seventeen = _unary("negate", depth_sixteen)
    with pytest.raises(ValueError, match="depth"):
        compile_expression(depth_seventeen, variable_count=0)


def test_expression_tree_counts_dag_occurrences_toward_node_limit() -> None:
    """Caching a shared child by identity would let a DAG bypass the 256-node budget."""
    shared_leaf = _constant(1)
    nodes_255 = _balanced_add_tree(shared_leaf, 128)
    nodes_256 = _unary("negate", nodes_255)
    assert compile_expression(nodes_256, variable_count=0)(np.array([])) == -128.0

    nodes_257 = _balanced_add_tree(shared_leaf, 129)
    with pytest.raises(ValueError, match="node"):
        compile_expression(nodes_257, variable_count=0)


def test_expression_tree_rejects_self_reference_without_recursing_forever() -> None:
    """A cyclic Mapping must fail deterministically instead of exhausting recursion."""
    node: dict[str, object] = {"op": "negate"}
    node["args"] = [node]

    with pytest.raises(ValueError, match="cyclic"):
        compile_expression(node, variable_count=0)


@pytest.mark.parametrize(
    ("node", "values"),
    [
        (_binary("divide", _constant(1), _constant(0)), []),
        (_binary("power", _constant(0), _constant(-1)), []),
        (_unary("log", _variable()), [0.0]),
        (_unary("log", _variable()), [-1.0]),
        (_unary("sqrt", _variable()), [-1.0]),
        (_unary("exp", _variable()), [1000.0]),
        (_binary("multiply", _variable(), _variable(1)), [1e308, 1e308]),
    ],
)
def test_expression_tree_closes_domain_and_overflow_failures(
    node: dict[str, object], values: list[float]
) -> None:
    """Domain and overflow errors must become ValueError rather than NaN or infinity."""
    fn = compile_expression(node, variable_count=len(values))

    with pytest.raises(ValueError):
        fn(np.asarray(values))


@pytest.mark.parametrize("values", [[1.0, 2.0], [[1.0]], [np.nan]])
def test_expression_tree_rejects_invalid_runtime_variable_vectors(values: object) -> None:
    """Wrong-shaped or non-finite runtime inputs cannot produce a trustworthy float."""
    fn = compile_expression(_variable(), variable_count=1)

    with pytest.raises(ValueError, match="variables"):
        fn(np.asarray(values))
