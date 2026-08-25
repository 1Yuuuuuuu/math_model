from __future__ import annotations

import pytest

from cumcm_toolkit.models import execution
from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import CapabilityRegistry, ModelSpec


CARD = "shared/knowledge/model-cards/statistics/anova.md"
RAW = {
    "parameters": {},
    "input_summary": {"rows": 2},
    "result": {"mean": 1.5},
    "diagnostics": {},
    "warnings": [],
    "seed": None,
}


def test_execute_routes_and_wraps_json(monkeypatch, project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)
    registry.register(
        ModelSpec("probe-model", "statistics", CARD, True, False, ("x",), lambda p: RAW)
    )
    monkeypatch.setattr(execution, "get_spec", registry.get)

    result = execute("probe-model", {"x": [1, 2]})

    assert result["model_id"] == "probe-model"
    assert result["executor"] == "statistics"
    assert result["status"] == "succeeded"


def test_execute_deep_copies_payload_before_invoking_model(monkeypatch, project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)

    def mutate_payload(payload):
        payload["x"].append(3)
        return RAW

    registry.register(ModelSpec("copy-model", "statistics", CARD, True, False, ("x",), mutate_payload))
    monkeypatch.setattr(execution, "get_spec", registry.get)
    payload = {"x": [1, 2]}

    execute("copy-model", payload)

    assert payload == {"x": [1, 2]}


@pytest.mark.parametrize(
    ("model_id", "payload", "stage"),
    [
        ("unknown-model", {}, "specification"),
        ("probe-model", [], "payload"),
        ("probe-model", {}, "payload fields"),
    ],
)
def test_execute_reports_model_and_stage_for_input_failures(
    monkeypatch, project_root, model_id: str, payload: object, stage: str
) -> None:
    registry = CapabilityRegistry(repository_root=project_root)
    registry.register(ModelSpec("probe-model", "statistics", CARD, True, False, ("x",), lambda p: RAW))
    monkeypatch.setattr(execution, "get_spec", registry.get)

    with pytest.raises(ValueError, match=rf"{model_id}.*{stage}"):
        execute(model_id, payload)


def test_execute_wraps_expected_executor_errors_with_execution_stage(monkeypatch, project_root) -> None:
    registry = CapabilityRegistry(repository_root=project_root)

    def fail(_: object) -> object:
        raise ArithmeticError("singular matrix")

    registry.register(ModelSpec("failing-model", "statistics", CARD, True, False, ("x",), fail))
    monkeypatch.setattr(execution, "get_spec", registry.get)

    with pytest.raises(ValueError, match=r"failing-model.*execution"):
        execute("failing-model", {"x": [1, 2]})
