from __future__ import annotations

import json
from pathlib import Path

import pytest

from cumcm_toolkit.workflow.gates import (
    index_decisions,
    index_review_bundles,
    validate_gate_decision,
)


ROOT = Path(__file__).resolve().parents[3]


def _decision(**changes: object) -> dict[str, object]:
    value = {
        "schema_version": "2.0",
        "decision_id": "dec_problem_approval",
        "gate": "gate_1_problem",
        "outcome": "approved",
        "selected_option": "Approve problem decomposition",
        "rationale": "Human checked the artifact.",
        "artifact_ids": ["art_problem_analysis"],
        "decided_by": "human",
        "decided_at": "2026-09-10T10:00:00+08:00",
    }
    value.update(changes)
    return value


def test_decision_index_requires_contract_valid_unique_human_records() -> None:
    decision = _decision()
    assert index_decisions([decision]) == {"dec_problem_approval": decision}
    with pytest.raises(ValueError, match="duplicate"):
        index_decisions([decision, decision])
    with pytest.raises(ValueError, match="contract"):
        index_decisions([_decision(decided_by="agent")])
    with pytest.raises(ValueError, match="contract"):
        index_decisions([_decision(outcome="maybe")])


def test_gate4_decision_must_bind_every_reviewed_bundle_artifact() -> None:
    decision = _decision(
        decision_id="dec_submission_approval",
        gate="gate_4_submission",
        artifact_ids=["art_unreviewed_paper"],
    )
    event = {
        "gate": "gate_4_submission",
        "stage": "review",
        "decision_id": "dec_submission_approval",
        "outcome": "approved",
        "artifact_ids": ["art_unreviewed_paper"],
    }
    bundle = {
        "bundle_id": "review_bundle_0123456789abcdef",
        "readiness": "ready_for_phase_6",
        "reviewed_artifact_ids": ["art_final_paper"],
    }
    with pytest.raises(ValueError, match="reviewed artifacts"):
        validate_gate_decision(
            {"stage": "review", "latest_artifact_ids": ["art_unreviewed_paper", "art_final_paper"]},
            event,
            {"dec_submission_approval": decision},
            attached_bundle_id="review_bundle_0123456789abcdef",
            review_bundles={"review_bundle_0123456789abcdef": bundle},
        )


def test_review_bundle_id_must_match_its_canonical_identity() -> None:
    bundle = json.loads(
        (ROOT / "shared/fixtures/contracts/valid/review-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert index_review_bundles([bundle]) == {bundle["bundle_id"]: bundle}
    changed = {**bundle, "reviewed_artifact_ids": ["art_different_paper"]}
    with pytest.raises(ValueError, match="identity"):
        index_review_bundles([changed])
