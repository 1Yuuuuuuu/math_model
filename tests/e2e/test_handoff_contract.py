from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.codex.handoff import complete_handoff, model_review_inputs
from cumcm_toolkit.artifacts.index import index_artifacts
from cumcm_toolkit.evidence.linker import link_claim
from cumcm_toolkit.experiments.manifest import create_experiment_record
from cumcm_toolkit.review.engine import load_rubric, review
from cumcm_toolkit.review.inputs import build_model_inputs


ROOT = Path(__file__).resolve().parents[2]
HANDOFF_TYPES = (
    "problem-analysis",
    "data-audit",
    "model-selection",
    "solver-run",
    "sensitivity-report",
)


def _traceability_bundle(tmp_path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    (tmp_path / "input.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (tmp_path / "solver.py").write_text("print('verified')\n", encoding="utf-8")
    for artifact_type in HANDOFF_TYPES:
        payload = {"status": "complete"}
        if artifact_type == "model-selection":
            payload.update(
                {
                    "baseline": "mean predictor",
                    "candidate_comparison": ["mean predictor", "linear regression"],
                    "validation_plan": {"metric": "rmse", "split": "held-out"},
                }
            )
        (tmp_path / f"{artifact_type}.json").write_text(
            json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
        )

    artifacts = index_artifacts(tmp_path)
    by_path = {record["path"]: record for record in artifacts}
    experiment = create_experiment_record(
        input_artifact_ids=[by_path["input.csv"]["artifact_id"]],
        code_artifact_id=by_path["solver.py"]["artifact_id"],
        parameters={"model": "linear-regression"},
        random_seed=7,
        status="succeeded",
        output_artifact_ids=[
            by_path[f"{artifact_type}.json"]["artifact_id"]
            for artifact_type in HANDOFF_TYPES
        ],
        metrics={"r2": 1.0},
        project_root=ROOT,
    )
    links = [
        link_claim(
            claim_id=f"clm_{artifact_type.replace('-', '_')}",
            claim_text=f"Traceable {artifact_type}",
            artifact_id=by_path[f"{artifact_type}.json"]["artifact_id"],
            experiment_id=experiment["experiment_id"],
            locator={"kind": "json_pointer", "value": "/status"},
            boundary="Only supports the recorded handoff status.",
        )
        for artifact_type in HANDOFF_TYPES
    ]
    return artifacts, [experiment], links


def _handoff(
    tmp_path: Path,
    artifact_type: str,
    artifacts: list[dict],
    experiments: list[dict],
    links: list[dict],
) -> dict[str, object]:
    return complete_handoff(
        artifact_type,
        outputs=[f"{artifact_type}.json"],
        evidence=[f"clm_{artifact_type.replace('-', '_')}"],
        workspace_root=tmp_path,
        artifact_records=artifacts,
        experiment_records=experiments,
        evidence_links=links,
    )


def test_complete_handoff_rejects_unknown_type_empty_or_unresolved_evidence(
    tmp_path: Path,
) -> None:
    artifacts, experiments, links = _traceability_bundle(tmp_path)
    kwargs = {
        "workspace_root": tmp_path,
        "artifact_records": artifacts,
        "experiment_records": experiments,
        "evidence_links": links,
    }
    with pytest.raises(ValueError, match="artifact_type"):
        complete_handoff("unknown-artifact", outputs=["x.json"], evidence=["clm_xxx"], **kwargs)
    with pytest.raises(ValueError, match="evidence"):
        complete_handoff("problem-analysis", outputs=["problem-analysis.json"], evidence=[], **kwargs)
    with pytest.raises(ValueError, match="unresolved evidence"):
        complete_handoff(
            "problem-analysis",
            outputs=["problem-analysis.json"],
            evidence=["clm_format_only"],
            **kwargs,
        )


def test_complete_handoff_rejects_changed_or_unindexed_output(tmp_path: Path) -> None:
    artifacts, experiments, links = _traceability_bundle(tmp_path)
    (tmp_path / "problem-analysis.json").write_text('{"status":"changed"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        _handoff(tmp_path, "problem-analysis", artifacts, experiments, links)

    (tmp_path / "not-indexed.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not indexed"):
        complete_handoff(
            "problem-analysis",
            outputs=["not-indexed.json"],
            evidence=["clm_problem_analysis"],
            workspace_root=tmp_path,
            artifact_records=artifacts,
            experiment_records=experiments,
            evidence_links=links,
        )


def test_model_review_inputs_bridge_five_complete_handoffs(tmp_path: Path) -> None:
    artifacts, experiments, links = _traceability_bundle(tmp_path)
    handoffs = [
        _handoff(tmp_path, artifact_type, artifacts, experiments, links)
        for artifact_type in HANDOFF_TYPES
    ]
    inputs = model_review_inputs(handoffs)
    assert set(inputs) == {
        "problem_analysis",
        "data_audit",
        "model_selection",
        "solver_run",
        "sensitivity_report",
        "evidence_refs",
    }
    assert inputs["evidence_refs"] == sorted(link["claim_id"] for link in links)


def test_model_review_inputs_rejects_missing_or_blocked_handoff(tmp_path: Path) -> None:
    artifacts, experiments, links = _traceability_bundle(tmp_path)
    handoffs = [
        _handoff(tmp_path, artifact_type, artifacts, experiments, links)
        for artifact_type in HANDOFF_TYPES[:-1]
    ]
    with pytest.raises(ValueError, match="missing handoffs"):
        model_review_inputs(handoffs)
    handoffs.append(_handoff(tmp_path, HANDOFF_TYPES[-1], artifacts, experiments, links))
    handoffs[1]["status"] = "blocked"
    with pytest.raises(ValueError, match="must be complete"):
        model_review_inputs(handoffs)


def test_real_handoffs_build_inputs_and_pass_model_review(tmp_path: Path) -> None:
    artifacts, experiments, links = _traceability_bundle(tmp_path)
    handoffs = [
        _handoff(tmp_path, artifact_type, artifacts, experiments, links)
        for artifact_type in HANDOFF_TYPES
    ]
    inputs = build_model_inputs(
        handoffs,
        workspace_root=tmp_path,
        artifact_records=artifacts,
        experiment_records=experiments,
        evidence_links=links,
    )
    rubric = load_rubric(ROOT / "shared/rubrics/model-quality.yaml")
    scores = [
        {
            "dimension_id": definition["dimension_id"],
            "score": 100,
            "rationale": "Verified against the indexed handoff evidence.",
            "evidence_refs": inputs["evidence_refs"],
        }
        for definition in rubric["scoring"]["dimensions"]
    ]

    report = review(inputs, rubric, score_dimensions=scores)

    assert report["status"] == "passed"
    assert inputs["model_selection"]["baseline"] == "mean predictor"
    assert inputs["sensitivity_report"]["status"] == "complete"
