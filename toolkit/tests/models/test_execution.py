from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

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


def test_runner_import_does_not_require_repository_root(tmp_path) -> None:
    """Eager public imports must not break the existing standalone runner import."""
    source_root = Path(__file__).resolve().parents[2] / "src"
    environment = dict(os.environ, PYTHONPATH=str(source_root))

    completed = subprocess.run(
        [sys.executable, "-c", "from cumcm_toolkit.models.runner import run_model"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


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
        raise ValueError("singular matrix")

    registry.register(ModelSpec("failing-model", "statistics", CARD, True, False, ("x",), fail))
    monkeypatch.setattr(execution, "get_spec", registry.get)

    with pytest.raises(ValueError, match=r"failing-model.*execution"):
        execute("failing-model", {"x": [1, 2]})


@pytest.mark.parametrize("error_type", [KeyError, TypeError])
def test_execute_preserves_unexpected_executor_errors(monkeypatch, project_root, error_type) -> None:
    """Programming errors in an executor must not be represented as model failures."""
    registry = CapabilityRegistry(repository_root=project_root)

    def fail(_: object) -> object:
        raise error_type("executor probe")

    registry.register(ModelSpec("probe-error", "statistics", CARD, True, False, ("x",), fail))
    monkeypatch.setattr(execution, "get_spec", registry.get)

    with pytest.raises(error_type, match="executor probe"):
        execute("probe-error", {"x": [1, 2]})


@pytest.mark.parametrize("error_type", [KeyError, TypeError])
def test_execute_preserves_unexpected_result_builder_errors(monkeypatch, project_root, error_type) -> None:
    """Programmer errors in result construction must remain visible to callers."""
    registry = CapabilityRegistry(repository_root=project_root)
    registry.register(ModelSpec("builder-error", "statistics", CARD, True, False, ("x",), lambda p: RAW))
    monkeypatch.setattr(execution, "get_spec", registry.get)

    def fail_builder(*args, **kwargs):
        raise error_type("builder probe")

    monkeypatch.setattr(execution, "build_success_result", fail_builder)

    with pytest.raises(error_type, match="builder probe"):
        execute("builder-error", {"x": [1, 2]})
