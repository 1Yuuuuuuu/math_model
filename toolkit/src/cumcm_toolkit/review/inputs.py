from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

from adapters.codex.handoff import model_review_inputs


ARTIFACT_ID = re.compile(r"art_[a-z0-9][a-z0-9_-]{2,63}\Z")
EXPERIMENT_ID = re.compile(r"exp_[a-z0-9][a-z0-9_-]{2,63}\Z")
CLAIM_ID = re.compile(r"clm_[a-z0-9][a-z0-9_-]{2,63}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
REPORT_STATUSES = frozenset({"ok", "failed"})


def _canonical_copy(value: object, field: str) -> object:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be finite JSON-compatible data: {exc}") from exc


def _index(
    records: Iterable[Mapping[str, object]], field: str, pattern: re.Pattern[str]
) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for record in records:
        copied = _canonical_copy(dict(record), field)
        assert isinstance(copied, dict)
        record_id = copied.get(field)
        if not isinstance(record_id, str) or not pattern.fullmatch(record_id):
            raise ValueError(f"invalid {field}")
        if record_id in indexed:
            raise ValueError(f"duplicate {field}: {record_id}")
        indexed[record_id] = copied
    return indexed


def _report(report: Mapping[str, object], name: str) -> dict[str, object]:
    copied = _canonical_copy(dict(report), name)
    assert isinstance(copied, dict)
    if copied.get("status") not in REPORT_STATUSES:
        raise ValueError(f"{name} status must be ok or failed")
    return copied


def _claim_ids(values: Iterable[str], field: str, *, required: bool = True) -> list[str]:
    result = list(values)
    if required and not result:
        raise ValueError(f"{field} must be non-empty")
    if (
        any(not isinstance(value, str) or not CLAIM_ID.fullmatch(value) for value in result)
        or len(result) != len(set(result))
    ):
        raise ValueError(f"{field} must contain unique claim IDs")
    return sorted(result)


def _claim_index(
    evidence_index: Mapping[str, Mapping[str, object]], claims: Iterable[str]
) -> dict[str, dict[str, object]]:
    copied = _canonical_copy(dict(evidence_index), "evidence_index")
    if not isinstance(copied, dict):
        raise ValueError("evidence_index must be a mapping")
    for claim_id in claims:
        record = copied.get(claim_id)
        if not isinstance(record, dict) or record.get("claim_id") != claim_id:
            raise ValueError(f"unresolved evidence in evidence_index: {claim_id}")
    return copied


def build_reproducibility_inputs(
    handoffs: Iterable[Mapping[str, object]],
    *,
    artifact_records: Iterable[Mapping[str, object]],
    experiment_records: Iterable[Mapping[str, object]],
    evidence_links: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    handoff_list = list(handoffs)
    normalized = model_review_inputs(handoff_list)
    artifacts = _index(artifact_records, "artifact_id", ARTIFACT_ID)
    experiments = _index(experiment_records, "experiment_id", EXPERIMENT_ID)
    links = _index(evidence_links, "claim_id", CLAIM_ID)
    artifacts_by_path: dict[str, dict[str, object]] = {}
    for artifact in artifacts.values():
        path = artifact.get("path")
        if not isinstance(path, str) or not path or path in artifacts_by_path:
            raise ValueError("artifact records require unique non-empty paths")
        artifacts_by_path[path] = artifact

    for experiment_id, experiment in experiments.items():
        if experiment.get("status") != "succeeded":
            raise ValueError(f"experiment must have succeeded: {experiment_id}")
        environment = experiment.get("environment")
        lock_hash = environment.get("lock_sha256") if isinstance(environment, dict) else None
        if not isinstance(lock_hash, str) or not SHA256.fullmatch(lock_hash):
            raise ValueError(f"experiment requires a valid lock hash: {experiment_id}")
        referenced_artifacts = [
            *(experiment.get("input_artifact_ids") or []),
            experiment.get("code_artifact_id"),
            *(experiment.get("output_artifact_ids") or []),
        ]
        if any(not isinstance(item, str) or item not in artifacts for item in referenced_artifacts):
            raise ValueError(f"experiment references a missing artifact: {experiment_id}")

    for claim_id, link in links.items():
        artifact_id = link.get("artifact_id")
        experiment_id = link.get("experiment_id")
        if artifact_id not in artifacts or experiment_id not in experiments:
            raise ValueError(f"broken evidence link: {claim_id}")
        if artifact_id not in experiments[str(experiment_id)].get("output_artifact_ids", []):
            raise ValueError(f"evidence link is not backed by an experiment output: {claim_id}")

    solver_experiments: set[str] = set()
    for handoff in handoff_list:
        outputs = handoff.get("outputs")
        evidence = handoff.get("evidence")
        if not isinstance(outputs, list) or any(path not in artifacts_by_path for path in outputs):
            raise ValueError(f"handoff output is not indexed: {handoff.get('artifact_type')}")
        if not isinstance(evidence, list):
            raise ValueError("handoff evidence must be a list")
        for evidence_id in evidence:
            if isinstance(evidence_id, str) and evidence_id.startswith("art_"):
                if evidence_id not in artifacts:
                    raise ValueError(f"unresolved artifact evidence: {evidence_id}")
            elif isinstance(evidence_id, str) and evidence_id.startswith("exp_"):
                if evidence_id not in experiments:
                    raise ValueError(f"unresolved experiment evidence: {evidence_id}")
                if handoff.get("artifact_type") == "solver-run":
                    solver_experiments.add(evidence_id)
            elif isinstance(evidence_id, str) and evidence_id.startswith("clm_"):
                if evidence_id not in links:
                    raise ValueError(f"unresolved claim evidence: {evidence_id}")
                if handoff.get("artifact_type") == "solver-run":
                    solver_experiments.add(str(links[evidence_id]["experiment_id"]))
            else:
                raise ValueError(f"invalid evidence identifier: {evidence_id}")
    if len(solver_experiments) != 1:
        raise ValueError("solver handoff must identify exactly one experiment")

    solver = dict(normalized["solver_run"])  # type: ignore[arg-type]
    solver_experiment_id = next(iter(solver_experiments))
    solver_experiment = experiments[solver_experiment_id]
    solver["experiment_id"] = solver_experiment_id
    solver["experiment_status"] = solver_experiment["status"]
    solver["lock_sha256"] = solver_experiment["environment"]["lock_sha256"]  # type: ignore[index]
    normalized["solver_run"] = solver
    normalized["artifact_index"] = artifacts
    normalized["experiment_index"] = experiments
    normalized["evidence_index"] = links
    result = _canonical_copy(normalized, "reproducibility inputs")
    assert isinstance(result, dict)
    return result


def _load_handoff_json(
    normalized: Mapping[str, object],
    handoff_key: str,
    *,
    workspace_root: Path,
) -> dict[str, object]:
    handoff = normalized.get(handoff_key)
    artifacts = normalized.get("artifact_index")
    if not isinstance(handoff, Mapping) or not isinstance(artifacts, Mapping):
        raise ValueError(f"missing normalized handoff or artifact index: {handoff_key}")
    outputs = handoff.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], str):
        raise ValueError(f"{handoff_key} must have exactly one JSON output")
    relative = PurePosixPath(outputs[0])
    if relative.suffix.lower() != ".json" or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{handoff_key} output must be a safe JSON path")
    artifact = next(
        (
            record
            for record in artifacts.values()
            if isinstance(record, Mapping) and record.get("path") == relative.as_posix()
        ),
        None,
    )
    if not isinstance(artifact, Mapping):
        raise ValueError(f"{handoff_key} output is not indexed")
    root = workspace_root.resolve()
    path = root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{handoff_key} output escapes workspace") from exc
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {handoff_key} output: {exc}") from exc
    if hashlib.sha256(content).hexdigest() != artifact.get("sha256"):
        raise ValueError(f"{handoff_key} output hash mismatch")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{handoff_key} output must be valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{handoff_key} output must be a JSON object")
    return payload


def build_model_inputs(
    handoffs: Iterable[Mapping[str, object]],
    *,
    workspace_root: Path,
    artifact_records: Iterable[Mapping[str, object]],
    experiment_records: Iterable[Mapping[str, object]],
    evidence_links: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Build model-gate inputs from the actual indexed handoff outputs."""
    normalized = build_reproducibility_inputs(
        handoffs,
        artifact_records=artifact_records,
        experiment_records=experiment_records,
        evidence_links=evidence_links,
    )
    model_selection = _load_handoff_json(
        normalized, "model_selection", workspace_root=workspace_root
    )
    sensitivity_payload = _load_handoff_json(
        normalized, "sensitivity_report", workspace_root=workspace_root
    )
    result = {
        "model_selection": model_selection,
        "sensitivity_report": {
            "status": normalized["sensitivity_report"]["status"],  # type: ignore[index]
            "report": sensitivity_payload,
        },
        "evidence_refs": normalized["evidence_refs"],
        "evidence_index": normalized["evidence_index"],
    }
    copied = _canonical_copy(result, "model review inputs")
    assert isinstance(copied, dict)
    return copied


def build_paper_inputs(
    *,
    evidence_report: Mapping[str, object],
    citation_report: Mapping[str, object],
    lint_report: Mapping[str, object],
    key_claim_ids: Iterable[str],
    claim_boundaries: Iterable[Mapping[str, object]],
    limitations: Iterable[str],
    evidence_index: Mapping[str, Mapping[str, object]],
    challenges: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    claims = _claim_ids(key_claim_ids, "key_claim_ids")
    boundaries = _canonical_copy([dict(item) for item in claim_boundaries], "claim_boundaries")
    challenge_list = _canonical_copy([dict(item) for item in challenges], "challenges")
    limitation_list = list(limitations)
    if any(not isinstance(item, str) or not item.strip() for item in limitation_list):
        raise ValueError("limitations must contain non-empty strings")
    for field, records in (("claim_boundaries", boundaries), ("challenges", challenge_list)):
        assert isinstance(records, list)
        for record in records:
            if not isinstance(record, dict) or not CLAIM_ID.fullmatch(str(record.get("claim_id", ""))):
                raise ValueError(f"{field} records require a valid claim_id")
    return {
        "paper_reports": {
            "evidence": _report(evidence_report, "evidence report"),
            "citations": _report(citation_report, "citation report"),
            "lint": _report(lint_report, "lint report"),
            "key_claim_ids": claims,
            "claim_boundaries": boundaries,
            "limitations": limitation_list,
            "challenges": challenge_list,
        },
        "evidence_refs": claims,
        "evidence_index": _claim_index(evidence_index, claims),
    }


def build_submission_inputs(
    *,
    build_report: Mapping[str, object],
    lint_report: Mapping[str, object],
    citation_report: Mapping[str, object],
    pdf_report: Mapping[str, object],
    source_sha256: str,
    pdf_sha256: str,
    annual_rule_verified: bool,
    evidence_refs: Iterable[str],
    evidence_index: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if not SHA256.fullmatch(source_sha256) or not SHA256.fullmatch(pdf_sha256):
        raise ValueError("source_sha256 and pdf_sha256 must be lowercase SHA-256 values")
    if annual_rule_verified is not True:
        raise ValueError("annual rule must be verified")
    claims = _claim_ids(evidence_refs, "evidence_refs")
    return {
        "submission_reports": {
            "build": _report(build_report, "build report"),
            "lint": _report(lint_report, "lint report"),
            "citations": _report(citation_report, "citation report"),
            "pdf": _report(pdf_report, "PDF report"),
            "source_hash": source_sha256,
            "pdf_hash": pdf_sha256,
            "annual_rule_verified": True,
        },
        "evidence_refs": claims,
        "evidence_index": _claim_index(evidence_index, claims),
    }
