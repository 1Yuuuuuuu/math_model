from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath


ARTIFACT_TYPES = frozenset(
    {
        "problem-analysis",
        "data-audit",
        "model-selection",
        "solver-run",
        "sensitivity-report",
        "literature-candidates",
        "model-review",
        "repro-review",
        "paper-review",
        "red-team-review",
        "submission-audit",
        "workflow-checkpoint",
    }
)
EVIDENCE_ID = re.compile(r"(?:clm|art|exp)_[a-z0-9][a-z0-9_-]{2,63}\Z")
MODEL_REVIEW_HANDOFFS = {
    "problem-analysis": "problem_analysis",
    "data-audit": "data_audit",
    "model-selection": "model_selection",
    "solver-run": "solver_run",
    "sensitivity-report": "sensitivity_report",
}


def _validate_artifact_type(artifact_type: str) -> None:
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"unsupported artifact_type: {artifact_type}")


def _unique_records(
    records: Iterable[Mapping[str, object]], id_field: str
) -> dict[str, Mapping[str, object]]:
    indexed: dict[str, Mapping[str, object]] = {}
    for record in records:
        record_id = record.get(id_field)
        if not isinstance(record_id, str) or not EVIDENCE_ID.fullmatch(record_id):
            raise ValueError(f"invalid {id_field} record")
        if record_id in indexed:
            raise ValueError(f"duplicate {id_field}: {record_id}")
        indexed[record_id] = record
    return indexed


def _validate_output_records(
    workspace_root: Path,
    outputs: Iterable[str],
    artifacts: Mapping[str, Mapping[str, object]],
) -> set[str]:
    root = workspace_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"workspace root not found: {root}")
    by_path: dict[str, Mapping[str, object]] = {}
    for record in artifacts.values():
        relative = record.get("path")
        if not isinstance(relative, str) or relative in by_path:
            raise ValueError("artifact records require unique portable paths")
        by_path[relative] = record

    output_ids: set[str] = set()
    for output in outputs:
        relative = PurePosixPath(output)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in output
            or ":" in output
        ):
            raise ValueError(f"unsafe output path: {output}")
        record = by_path.get(relative.as_posix())
        if record is None:
            raise ValueError(f"output is not indexed: {output}")
        path = root.joinpath(*relative.parts).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"output escapes workspace: {output}") from exc
        if not path.is_file():
            raise ValueError(f"output file is missing: {output}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != record.get("sha256"):
            raise ValueError(f"output hash mismatch: {output}")
        output_ids.add(str(record["artifact_id"]))
    return output_ids


def _validate_evidence_records(
    evidence: Iterable[str],
    output_ids: set[str],
    artifacts: Mapping[str, Mapping[str, object]],
    experiments: Mapping[str, Mapping[str, object]],
    links: Mapping[str, Mapping[str, object]],
) -> None:
    for evidence_id in evidence:
        linked_outputs: set[str]
        if evidence_id.startswith("art_"):
            if evidence_id not in artifacts:
                raise ValueError(f"unresolved evidence: {evidence_id}")
            linked_outputs = {evidence_id}
        elif evidence_id.startswith("exp_"):
            record = experiments.get(evidence_id)
            if record is None:
                raise ValueError(f"unresolved evidence: {evidence_id}")
            linked_outputs = set(record.get("output_artifact_ids", []))
        else:
            link = links.get(evidence_id)
            if link is None:
                raise ValueError(f"unresolved evidence: {evidence_id}")
            artifact_id = link.get("artifact_id")
            experiment_id = link.get("experiment_id")
            if artifact_id not in artifacts or experiment_id not in experiments:
                raise ValueError(f"broken evidence link: {evidence_id}")
            experiment_outputs = set(experiments[str(experiment_id)].get("output_artifact_ids", []))
            if artifact_id not in experiment_outputs:
                raise ValueError(f"evidence link is not an experiment output: {evidence_id}")
            linked_outputs = {str(artifact_id)}
        if not output_ids.intersection(linked_outputs):
            raise ValueError(f"evidence does not support a handoff output: {evidence_id}")


def _strings(values: Iterable[str], field: str, *, required: bool = False) -> list[str]:
    result = list(values)
    if required and not result:
        raise ValueError(f"{field} must be non-empty")
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{field} must contain non-empty strings")
    return result


def _handoff(
    status: str,
    artifact_type: str,
    *,
    inputs: Iterable[str] = (),
    outputs: Iterable[str] = (),
    evidence: Iterable[str] = (),
    missing_inputs: Iterable[str] = (),
    failed_step: str | None = None,
    resume_when: Iterable[str] = (),
) -> dict[str, object]:
    _validate_artifact_type(artifact_type)
    return {
        "status": status,
        "artifact_type": artifact_type,
        "inputs": list(inputs),
        "outputs": list(outputs),
        "evidence": list(evidence),
        "missing_inputs": list(missing_inputs),
        "failed_step": failed_step,
        "resume_when": list(resume_when),
    }


def complete_handoff(
    artifact_type: str,
    *,
    inputs: Iterable[str] = (),
    outputs: Iterable[str],
    evidence: Iterable[str],
    workspace_root: Path,
    artifact_records: Iterable[Mapping[str, object]],
    experiment_records: Iterable[Mapping[str, object]] = (),
    evidence_links: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    _validate_artifact_type(artifact_type)
    outputs = _strings(outputs, "outputs", required=True)
    evidence = _strings(evidence, "evidence", required=True)
    if any(not EVIDENCE_ID.fullmatch(value) for value in evidence):
        raise ValueError("evidence must contain clm_, art_, or exp_ identifiers")
    artifacts = _unique_records(artifact_records, "artifact_id")
    experiments = _unique_records(experiment_records, "experiment_id")
    links = _unique_records(evidence_links, "claim_id")
    output_ids = _validate_output_records(workspace_root, outputs, artifacts)
    _validate_evidence_records(evidence, output_ids, artifacts, experiments, links)
    return _handoff(
        "complete",
        artifact_type,
        inputs=_strings(inputs, "inputs"),
        outputs=outputs,
        evidence=evidence,
    )


def blocked_handoff(
    artifact_type: str,
    *,
    missing_inputs: Iterable[str] = (),
    failed_step: str | None = None,
    resume_when: Iterable[str] = (),
) -> dict[str, object]:
    _validate_artifact_type(artifact_type)
    missing = _strings(missing_inputs, "missing_inputs")
    if not missing and failed_step is None:
        raise ValueError("blocked handoff requires missing_inputs or failed_step")
    resume = list(resume_when) or ["provide the missing input or restore the failed capability"]
    return _handoff(
        "blocked",
        artifact_type,
        missing_inputs=missing,
        failed_step=failed_step,
        resume_when=resume,
    )


def model_review_inputs(handoffs: Iterable[Mapping[str, object]]) -> dict[str, object]:
    indexed: dict[str, Mapping[str, object]] = {}
    for handoff in handoffs:
        artifact_type = handoff.get("artifact_type")
        if artifact_type not in MODEL_REVIEW_HANDOFFS:
            raise ValueError(f"unsupported model-review handoff: {artifact_type}")
        if artifact_type in indexed:
            raise ValueError(f"duplicate model-review handoff: {artifact_type}")
        if handoff.get("status") != "complete":
            raise ValueError(f"handoff must be complete: {artifact_type}")
        indexed[str(artifact_type)] = handoff
    missing = sorted(set(MODEL_REVIEW_HANDOFFS) - set(indexed))
    if missing:
        raise ValueError(f"missing handoffs: {', '.join(missing)}")

    evidence_refs = sorted(
        {
            value
            for handoff in indexed.values()
            for value in handoff.get("evidence", [])
            if isinstance(value, str) and value.startswith("clm_") and EVIDENCE_ID.fullmatch(value)
        }
    )
    if not evidence_refs:
        raise ValueError("model review requires at least one clm_ evidence reference")
    result = {
        key: copy.deepcopy(indexed[artifact_type])
        for artifact_type, key in MODEL_REVIEW_HANDOFFS.items()
    }
    result["evidence_refs"] = evidence_refs
    return result
