from __future__ import annotations

import copy

import pytest

from cumcm_toolkit.review.inputs import (
    build_paper_inputs,
    build_reproducibility_inputs,
    build_submission_inputs,
)


SHA = "a" * 64


def _phase3() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    kinds = ["problem-analysis", "data-audit", "model-selection", "solver-run", "sensitivity-report"]
    artifacts = [
        {
            "artifact_id": f"art_{kind.replace('-', '_')}",
            "path": f"reports/{kind}.json",
            "sha256": SHA,
        }
        for kind in kinds
    ]
    artifacts.extend(
        [
            {"artifact_id": "art_input", "path": "data/input.csv", "sha256": SHA},
            {"artifact_id": "art_code", "path": "src/solve.py", "sha256": SHA},
        ]
    )
    experiment = {
        "experiment_id": "exp_solver_run",
        "input_artifact_ids": ["art_input"],
        "code_artifact_id": "art_code",
        "output_artifact_ids": ["art_solver_run"],
        "environment": {"python_version": "3.11", "lock_sha256": SHA},
        "status": "succeeded",
    }
    link = {
        "claim_id": "clm_solver_result",
        "artifact_id": "art_solver_run",
        "experiment_id": "exp_solver_run",
    }
    handoffs = []
    for kind in kinds:
        evidence = ["clm_solver_result"] if kind == "solver-run" else [f"art_{kind.replace('-', '_')}"]
        handoffs.append(
            {
                "status": "complete",
                "artifact_type": kind,
                "inputs": [],
                "outputs": [f"reports/{kind}.json"],
                "evidence": evidence,
                "missing_inputs": [],
                "failed_step": None,
                "resume_when": [],
            }
        )
    return handoffs, artifacts, [experiment], [link]


def test_valid_phase3_bundle_is_normalized() -> None:
    handoffs, artifacts, experiments, links = _phase3()
    result = build_reproducibility_inputs(
        handoffs,
        artifact_records=artifacts,
        experiment_records=experiments,
        evidence_links=links,
    )
    assert result["solver_run"]["experiment_id"] == "exp_solver_run"  # type: ignore[index]
    assert result["experiment_index"]["exp_solver_run"]["status"] == "succeeded"  # type: ignore[index]
    assert result["evidence_refs"] == ["clm_solver_result"]


@pytest.mark.parametrize("mutation", ["missing_artifact", "broken_link", "failed_experiment", "missing_lock"])
def test_phase3_invalid_references_fail_closed(mutation: str) -> None:
    handoffs, artifacts, experiments, links = _phase3()
    if mutation == "missing_artifact":
        artifacts.pop()
    elif mutation == "broken_link":
        links[0]["artifact_id"] = "art_unknown"
    elif mutation == "failed_experiment":
        experiments[0]["status"] = "failed"
    else:
        experiments[0]["environment"] = {"python_version": "3.11", "lock_sha256": ""}
    with pytest.raises(ValueError):
        build_reproducibility_inputs(
            handoffs,
            artifact_records=artifacts,
            experiment_records=experiments,
            evidence_links=links,
        )


def test_paper_inputs_expose_reports_and_reject_bad_claims() -> None:
    result = build_paper_inputs(
        evidence_report={"status": "ok", "unresolved": []},
        citation_report={"status": "ok", "errors": []},
        lint_report={"status": "ok", "issues": []},
        key_claim_ids=["clm_key_result"],
        claim_boundaries=[{"claim_id": "clm_key_result", "boundary": "test set only"}],
        limitations=["Small sample."],
        evidence_index={"clm_key_result": {"claim_id": "clm_key_result"}},
        challenges=[{"claim_id": "clm_key_result", "challenge": "Check leakage."}],
    )
    assert result["paper_reports"]["lint"]["status"] == "ok"  # type: ignore[index]
    with pytest.raises(ValueError, match="claim"):
        build_paper_inputs(
            evidence_report={"status": "ok", "unresolved": []},
            citation_report={"status": "ok"},
            lint_report={"status": "ok"},
            key_claim_ids=["not-a-claim"],
            claim_boundaries=[],
            limitations=["Known limit."],
            evidence_index={},
        )


def test_paper_report_statuses_are_strict() -> None:
    with pytest.raises(ValueError, match="status"):
        build_paper_inputs(
            evidence_report={"status": "unknown", "unresolved": []},
            citation_report={"status": "ok"},
            lint_report={"status": "ok"},
            key_claim_ids=["clm_key_result"],
            claim_boundaries=[{"claim_id": "clm_key_result"}],
            limitations=["Known limit."],
            evidence_index={"clm_key_result": {"claim_id": "clm_key_result"}},
        )


def test_submission_inputs_require_hash_rule_and_evidence() -> None:
    kwargs = {
        "build_report": {"status": "ok"},
        "lint_report": {"status": "ok"},
        "citation_report": {"status": "ok"},
        "pdf_report": {"status": "ok", "blank_pages": []},
        "source_sha256": SHA,
        "pdf_sha256": "b" * 64,
        "annual_rule_verified": True,
        "evidence_refs": ["clm_submission_ready"],
        "evidence_index": {
            "clm_submission_ready": {"claim_id": "clm_submission_ready"}
        },
    }
    result = build_submission_inputs(**kwargs)
    assert result["submission_reports"]["annual_rule_verified"] is True  # type: ignore[index]
    for field, value in (("source_sha256", "bad"), ("annual_rule_verified", False)):
        changed = copy.deepcopy(kwargs)
        changed[field] = value
        with pytest.raises(ValueError):
            build_submission_inputs(**changed)
