import json
import math

import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from cumcm_toolkit.models.result import build_success_result, normalize_json
from scripts.validate_contracts import load_json, make_validator


def test_success_result_is_finite_json_and_contract_valid(project_root) -> None:
    raw = {
        "parameters": {},
        "input_summary": {"rows": 2},
        "result": {"scores": np.array([0.25, 0.75])},
        "diagnostics": {},
        "warnings": ["later", "earlier", "later"],
        "seed": None,
    }

    result = build_success_result("topsis", "evaluation", raw, deterministic=True)

    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert result["result"]["scores"] == [0.25, 0.75]
    assert result["warnings"] == ["earlier", "later"]
    make_validator(
        load_json(project_root / "shared/contracts/model-execution.schema.json")
    ).validate(result)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), np.float64("-inf")])
def test_result_rejects_nonfinite_values(bad: object) -> None:
    with pytest.raises(ValueError, match="finite"):
        normalize_json({"value": bad}, "result")


def test_result_rejects_estimator_objects() -> None:
    with pytest.raises(ValueError, match="JSON"):
        normalize_json({"model": LinearRegression()}, "result")


def test_success_result_rejects_non_array_warnings() -> None:
    raw = {
        "parameters": {},
        "input_summary": {},
        "result": {},
        "diagnostics": {},
        "warnings": "not-an-array",
        "seed": None,
    }

    with pytest.raises(ValueError, match="warnings"):
        build_success_result("topsis", "evaluation", raw, deterministic=True)


def test_offline_validator_rejects_overflow_json_number_as_a_type_error(project_root) -> None:
    schema = load_json(project_root / "shared/contracts/model-execution.schema.json")
    fixture = load_json(
        project_root
        / "shared/fixtures/contracts/invalid/model-execution-nonfinite-result.json"
    )

    assert math.isinf(fixture["result"]["nonfinite"])
    number_errors = list(
        make_validator({"type": "number"}).iter_errors(fixture["result"]["nonfinite"])
    )
    assert [(tuple(error.absolute_path), error.validator) for error in number_errors] == [
        ((), "type")
    ]
    assert make_validator({"type": "number"}).is_valid(1.25)
    assert not make_validator({"type": "number"}).is_valid("1.25")

    errors = list(make_validator(schema).iter_errors(fixture))
    assert [(tuple(error.absolute_path), error.validator) for error in errors] == [
        (("result", "nonfinite"), "oneOf")
    ]
