from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from pathlib import Path

from cumcm_toolkit.review.bundle import _bundle_validator
from cumcm_toolkit.review.engine import canonical_digest
from scripts.validate_contracts import load_json, make_validator


_ROOT = Path(__file__).resolve().parents[4]
_DECISION_VALIDATOR = make_validator(
    load_json(_ROOT / "shared/contracts/decision.schema.json")
)

GATE_STAGES = {
    "gate_1_problem": ("intake", "model_design"),
    "gate_2_model": ("model_design", "solve"),
    "gate_3_outline": ("outline", "write"),
    "gate_4_submission": ("review", "submission"),
}


def index_decisions(
    decisions: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for value in decisions:
        if not isinstance(value, Mapping):
            raise ValueError("decision must be a mapping")
        decision = copy.deepcopy(dict(value))
        errors = sorted(
            _DECISION_VALIDATOR.iter_errors(decision), key=lambda error: list(error.path)
        )
        if errors:
            location = ".".join(str(part) for part in errors[0].path) or "decision"
            raise ValueError(f"decision contract failed at {location}: {errors[0].message}")
        if decision.get("schema_version") != "2.0":
            raise ValueError("decision schema_version 1.0 must be migrated to 2.0 before workflow use")
        decision_id = str(decision["decision_id"])
        if decision_id in indexed:
            raise ValueError(f"duplicate decision_id: {decision_id}")
        indexed[decision_id] = decision
    return indexed


def index_review_bundles(
    bundles: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    validator = _bundle_validator()
    for value in bundles:
        if not isinstance(value, Mapping):
            raise ValueError("review bundle must be a mapping")
        bundle = copy.deepcopy(dict(value))
        errors = sorted(validator.iter_errors(bundle), key=lambda error: list(error.path))
        if errors:
            location = ".".join(str(part) for part in errors[0].path) or "bundle"
            raise ValueError(f"review bundle contract failed at {location}: {errors[0].message}")
        bundle_id = str(bundle["bundle_id"])
        identity = {
            key: bundle[key]
            for key in (
                "report_ids",
                "report_digests",
                "reviewed_artifact_ids",
                "readiness",
                "open_blocking_findings",
                "errors",
            )
        }
        expected_id = f"review_bundle_{canonical_digest(identity)[:16]}"
        if bundle_id != expected_id:
            raise ValueError("review bundle identity does not match its content")
        if bundle_id in indexed:
            raise ValueError(f"duplicate review bundle id: {bundle_id}")
        indexed[bundle_id] = bundle
    return indexed


def validate_gate_decision(
    state: Mapping[str, object],
    event: Mapping[str, object],
    decisions: Mapping[str, Mapping[str, object]],
    *,
    attached_bundle_id: str | None,
    review_bundles: Mapping[str, Mapping[str, object]],
) -> tuple[str, str]:
    gate = str(event.get("gate"))
    if gate not in GATE_STAGES:
        raise ValueError(f"invalid human gate: {gate}")
    current_stage, next_stage = GATE_STAGES[gate]
    if state.get("stage") != current_stage or event.get("stage") != current_stage:
        raise ValueError(f"{gate} cannot run outside stage {current_stage}")
    decision_id = event.get("decision_id")
    decision = decisions.get(str(decision_id))
    if decision is None:
        raise ValueError(f"unresolved human decision: {decision_id}")
    if decision["gate"] != gate:
        raise ValueError("decision gate does not match event gate")
    if decision["outcome"] != event.get("outcome"):
        raise ValueError("decision outcome does not match event outcome")
    event_artifacts = set(event.get("artifact_ids", []))
    decision_artifacts = set(decision["artifact_ids"])
    if event_artifacts != decision_artifacts:
        raise ValueError("decision artifacts do not match gate event artifacts")
    current_artifacts = set(state.get("latest_artifact_ids", []))
    if not decision_artifacts.issubset(current_artifacts):
        raise ValueError("decision refers to artifacts outside the current workflow state")
    if gate == "gate_4_submission":
        if attached_bundle_id is None:
            raise ValueError("gate_4_submission requires an attached review bundle")
        bundle = review_bundles.get(attached_bundle_id)
        if bundle is None or bundle.get("readiness") != "ready_for_phase_6":
            raise ValueError("gate_4_submission requires a ready current review bundle")
        reviewed_artifacts = set(bundle.get("reviewed_artifact_ids", []))
        if not reviewed_artifacts.issubset(decision_artifacts):
            raise ValueError(
                "gate_4_submission decision must bind all reviewed artifacts"
            )
    return str(event["outcome"]), next_stage
