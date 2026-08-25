from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from adapters.codex.handoff import blocked_handoff, complete_handoff
from adapters.codex.routing import solver_execution_mode
from cumcm_toolkit.artifacts.index import index_artifacts
from cumcm_toolkit.evidence.linker import link_claim
from cumcm_toolkit.evaluation.metrics import regression_metrics
from cumcm_toolkit.evaluation.sensitivity import sensitivity_report
from cumcm_toolkit.experiments.manifest import create_experiment_record
from cumcm_toolkit.models.runner import run_model


ROOT = Path(__file__).resolve().parents[2]


def test_supported_prediction_flow_has_traceable_handoffs(tmp_path: Path) -> None:
    x = np.arange(1.0, 9.0).reshape(-1, 1)
    y = 3.0 * x[:, 0] + 2.0
    run = run_model("linear-regression", x, y, seed=7)
    metrics = regression_metrics(y, run["fitted"].predict(x))
    report = sensitivity_report(
        base_params={"slope": 3.0},
        perturb={"slope": [2.7, 3.0, 3.3]},
        evaluate=lambda p: regression_metrics(y, p["slope"] * x[:, 0] + 2.0)["r2"],
    )

    outputs = {
        "questions.json": {"subproblems": ["fit a linear trend"]},
        "model-selection.json": {"model_id": "linear-regression", "baseline": "mean"},
        "experiment.json": {"model_id": "linear-regression", "metrics": metrics},
        "sensitivity.json": report,
    }
    for relative, payload in outputs.items():
        (tmp_path / relative).write_text(
            json.dumps(payload, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
        )
    (tmp_path / "input.csv").write_text("x,y\n1,5\n2,8\n", encoding="utf-8")
    (tmp_path / "solver.py").write_text("# verified linear regression runner\n", encoding="utf-8")

    artifacts = index_artifacts(tmp_path)
    by_path = {record["path"]: record for record in artifacts}
    experiment = create_experiment_record(
        input_artifact_ids=[by_path["input.csv"]["artifact_id"]],
        code_artifact_id=by_path["solver.py"]["artifact_id"],
        parameters={"model_id": "linear-regression"},
        random_seed=7,
        status="succeeded",
        output_artifact_ids=[by_path[path]["artifact_id"] for path in outputs],
        metrics={"r2": metrics["r2"]},
        project_root=ROOT,
    )
    handoff_specs = (
        ("problem-analysis", "questions.json", "clm_problem_analysis"),
        ("model-selection", "model-selection.json", "clm_model_selection"),
        ("solver-run", "experiment.json", "clm_solver_result"),
        ("sensitivity-report", "sensitivity.json", "clm_sensitivity_result"),
    )
    links = [
        link_claim(
            claim_id=claim_id,
            claim_text=f"Traceable output {relative}",
            artifact_id=by_path[relative]["artifact_id"],
            experiment_id=experiment["experiment_id"],
            locator={"kind": "file_region", "value": relative},
            boundary="Supports only the saved output.",
        )
        for _, relative, claim_id in handoff_specs
    ]
    handoffs = [
        complete_handoff(
            artifact_type,
            outputs=[relative],
            evidence=[claim_id],
            workspace_root=tmp_path,
            artifact_records=artifacts,
            experiment_records=[experiment],
            evidence_links=links,
        )
        for artifact_type, relative, claim_id in handoff_specs
    ]

    assert [item["artifact_type"] for item in handoffs] == [
        "problem-analysis", "model-selection", "solver-run", "sensitivity-report"
    ]
    assert all((tmp_path / item["outputs"][0]).is_file() for item in handoffs)
    assert metrics["r2"] == pytest.approx(1.0)
    assert report["parameters"]["slope"]["results"]


def test_missing_data_and_unsupported_model_are_blocked_without_outputs() -> None:
    missing = blocked_handoff("data-audit", missing_inputs=["data file"], failed_step="load data")
    unsupported = blocked_handoff(
        "solver-run", missing_inputs=["verified ARIMA runner"], failed_step="capability check"
    )
    for handoff in (missing, unsupported):
        assert handoff["status"] == "blocked"
        assert handoff["outputs"] == []
        assert handoff["resume_when"]


def test_zero_valid_sensitivity_points_fail_closed() -> None:
    with pytest.raises(ValueError, match="no parameters perturbed"):
        sensitivity_report(
            base_params={"known": 1.0},
            perturb={"unknown": [0.5, 1.5]},
            evaluate=lambda _: 1.0,
        )


@pytest.mark.parametrize(
    "model_id",
    ["entropy-weight", "topsis", "linear-regression", "linear-programming"],
)
def test_verified_solver_capabilities_are_executable(model_id: str) -> None:
    assert solver_execution_mode(model_id) == "execute"


@pytest.mark.parametrize("model_id", ["arima", "kmeans", "heuristic"])
def test_unverified_solver_capabilities_are_plan_only(model_id: str) -> None:
    assert solver_execution_mode(model_id) == "plan-only"
