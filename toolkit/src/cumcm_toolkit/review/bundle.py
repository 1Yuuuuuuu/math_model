from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from rfc3339_validator import validate_rfc3339

from cumcm_toolkit.experiments.manifest import utc_now_rfc3339
from cumcm_toolkit.review.engine import (
    _report_validator,
    _validate_rubric,
    canonical_digest,
    review,
)
from cumcm_toolkit.review.scorecard import evaluate_scorecard
from cumcm_toolkit.review.severity import gate_status, is_blocking
from scripts.validate_contracts import make_validator


REVIEW_SLOTS: tuple[str, ...] = (
    "submission",
    "reproducibility",
    "model",
    "paper",
    "red_team",
)
EXPECTED_RUBRICS = {
    "submission": "submission",
    "reproducibility": "reproducibility",
    "model": "model-quality",
    "paper": "paper-quality",
    "red_team": "red-team",
}
EXPECTED_GATES = {
    "submission": "hard",
    "reproducibility": "reproducibility",
    "model": "model",
    "paper": "paper",
    "red_team": "red_team",
}
REVIEW_ID = re.compile(r"review_[a-f0-9]{16}\Z")
ARTIFACT_ID = re.compile(r"art_[a-z0-9][a-z0-9_-]{2,63}\Z")


def _bundle_validator() -> Draft202012Validator:
    root = Path(__file__).resolve().parents[4]
    schema = json.loads(
        (root / "shared/contracts/review-bundle.schema.json").read_text(encoding="utf-8")
    )
    return make_validator(schema)


def build_review_bundle(
    *,
    reports: Mapping[str, Mapping[str, object]],
    current_inputs: Mapping[str, dict[str, object]],
    rubrics: Mapping[str, dict[str, object]],
    reviewed_files: Mapping[str, Iterable[Path]],
    reviewed_artifact_ids: Iterable[str],
    file_root: Path,
    score_dimensions: Mapping[str, Iterable[Mapping[str, object]]] | None = None,
    reviewer_findings: Mapping[str, Iterable[Mapping[str, object]]] | None = None,
    created_at: str | None = None,
) -> dict[str, object]:
    timestamp = created_at if created_at is not None else utc_now_rfc3339()
    if not isinstance(timestamp, str) or not validate_rfc3339(timestamp):
        raise ValueError("created_at must be an RFC 3339 date-time")
    artifact_ids = list(reviewed_artifact_ids)
    if (
        not artifact_ids
        or len(artifact_ids) != len(set(artifact_ids))
        or any(not isinstance(value, str) or not ARTIFACT_ID.fullmatch(value) for value in artifact_ids)
    ):
        raise ValueError("reviewed_artifact_ids must contain unique artifact IDs")
    artifact_ids = sorted(artifact_ids)
    score_material = dict(score_dimensions or {})
    finding_material = dict(reviewer_findings or {})
    report_ids: dict[str, object] = {slot: None for slot in REVIEW_SLOTS}
    report_digests: dict[str, object] = {slot: None for slot in REVIEW_SLOTS}
    errors: list[str] = []
    stale_or_failed = False
    blocking_findings: set[str] = set()

    expected_slots = set(REVIEW_SLOTS)
    for name, supplied in (
        ("reports", set(reports)),
        ("current_inputs", set(current_inputs)),
        ("rubrics", set(rubrics)),
        ("reviewed_files", set(reviewed_files)),
    ):
        missing = sorted(expected_slots - supplied)
        extra = sorted(supplied - expected_slots)
        if missing:
            errors.append(f"{name} missing slots: {', '.join(missing)}")
        if extra:
            errors.append(f"{name} has unknown slots: {', '.join(extra)}")
    if not file_root.resolve().is_dir():
        errors.append("file_root is missing or is not a directory")

    report_validator = _report_validator()
    for slot in REVIEW_SLOTS:
        report_value = reports.get(slot)
        if not isinstance(report_value, Mapping):
            continue
        report = dict(report_value)
        validation_errors = sorted(
            report_validator.iter_errors(report), key=lambda error: list(error.path)
        )
        if validation_errors:
            errors.append(f"{slot}: invalid review report: {validation_errors[0].message}")
            continue
        try:
            report_digests[slot] = canonical_digest(report)
        except ValueError as exc:
            errors.append(f"{slot}: report is not canonical JSON: {exc}")
            continue
        report_id = report.get("review_id")
        if isinstance(report_id, str) and REVIEW_ID.fullmatch(report_id):
            report_ids[slot] = report_id
        if report.get("rubric_id") != EXPECTED_RUBRICS[slot]:
            errors.append(f"{slot}: report has the wrong rubric_id")
            continue
        if report.get("review_gate") != EXPECTED_GATES[slot]:
            errors.append(f"{slot}: report has the wrong review_gate")
            continue
        if slot not in rubrics or slot not in current_inputs or slot not in reviewed_files:
            continue
        try:
            rubric = _validate_rubric(rubrics[slot])
        except ValueError as exc:
            errors.append(f"{slot}: invalid rubric: {exc}")
            continue
        if rubric["rubric_id"] != EXPECTED_RUBRICS[slot]:
            errors.append(f"{slot}: current rubric does not match the slot")
            continue
        scores = list(score_material[slot]) if slot in score_material else None
        if "scoring" in rubric and scores is None:
            errors.append(f"{slot}: current score dimensions are required")
            continue
        if "scoring" not in rubric and scores is not None:
            errors.append(f"{slot}: score dimensions supplied for an unscored rubric")
            continue
        if scores is not None:
            try:
                expected_scorecard = evaluate_scorecard(rubric, scores)
            except ValueError as exc:
                errors.append(f"{slot}: invalid current score dimensions: {exc}")
                continue
            if report.get("scorecard") != expected_scorecard:
                stale_or_failed = True
        external = list(finding_material.get(slot, ()))
        try:
            rebuilt = review(
                current_inputs[slot],
                rubric,
                capabilities=set(rubric["requires_capabilities"]),
                reviewed_at=str(report["reviewed_at"]),
                reviewed_files=list(reviewed_files[slot]),
                file_root=file_root,
                score_dimensions=scores,
                reviewer_findings=external,
            )
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"{slot}: cannot revalidate current review material: {exc}")
            continue
        if canonical_digest(rebuilt) != canonical_digest(report):
            stale_or_failed = True
        if report["status"] != gate_status(report["findings"], list(report["errors"])):
            errors.append(f"{slot}: status is inconsistent with findings and errors")
            continue
        if report["status"] != "passed":
            stale_or_failed = True
        for finding in report["findings"]:
            if finding.get("status") == "open" and is_blocking(
                str(finding.get("severity")), str(finding.get("status"))
            ):
                blocking_findings.add(str(finding["finding_id"]))
                stale_or_failed = True

    errors = sorted(set(errors))
    if errors:
        readiness = "blocked"
    elif stale_or_failed:
        readiness = "not_ready"
    else:
        readiness = "ready_for_phase_6"
    identity_material: dict[str, Any] = {
        "report_ids": report_ids,
        "report_digests": report_digests,
        "reviewed_artifact_ids": artifact_ids,
        "readiness": readiness,
        "open_blocking_findings": sorted(blocking_findings),
        "errors": errors,
    }
    bundle: dict[str, object] = {
        "schema_version": "1.0",
        "bundle_id": f"review_bundle_{canonical_digest(identity_material)[:16]}",
        **identity_material,
        "created_at": timestamp,
    }
    validation_errors = sorted(
        _bundle_validator().iter_errors(bundle), key=lambda error: list(error.path)
    )
    if validation_errors:
        raise ValueError(f"generated review bundle violates contract: {validation_errors[0].message}")
    return bundle
