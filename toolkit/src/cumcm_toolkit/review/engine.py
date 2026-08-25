from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from rfc3339_validator import validate_rfc3339

from cumcm_toolkit.experiments.manifest import utc_now_rfc3339
from cumcm_toolkit.review.scorecard import evaluate_scorecard, validate_scoring_definition
from cumcm_toolkit.review.severity import gate_status, validate_severity
from scripts.validate_contracts import make_validator


CHECKERS = frozenset(
    {"required_path", "non_empty", "equals", "all_present", "hash_matches", "covers_claims"}
)
REVIEW_GATES = frozenset({"hard", "reproducibility", "model", "paper", "red_team"})
IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{2,55}\Z")
CLAIM_ID = re.compile(r"clm_[a-z0-9][a-z0-9_-]{2,63}\Z")
_MISSING = object()


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate YAML key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def canonical_digest(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value cannot be represented as canonical JSON: {exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validate_rubric(rubric: object) -> dict[str, Any]:
    if not isinstance(rubric, dict):
        raise ValueError("rubric must be a mapping")
    required = {"rubric_id", "version", "review_gate", "requires_capabilities", "rules"}
    missing = sorted(required - rubric.keys())
    if missing:
        raise ValueError(f"rubric missing fields: {', '.join(missing)}")
    if not isinstance(rubric["rubric_id"], str) or not IDENTIFIER.fullmatch(rubric["rubric_id"]):
        raise ValueError("invalid rubric_id")
    if rubric["version"] != "1.0":
        raise ValueError("unsupported rubric version")
    if rubric["review_gate"] not in REVIEW_GATES:
        raise ValueError("invalid review_gate")
    if not isinstance(rubric["requires_capabilities"], list) or any(
        not isinstance(value, str) or not value for value in rubric["requires_capabilities"]
    ):
        raise ValueError("requires_capabilities must contain strings")
    if not isinstance(rubric["rules"], list) or not rubric["rules"]:
        raise ValueError("rubric rules must be a non-empty list")
    if "scoring" in rubric:
        validate_scoring_definition(rubric["scoring"])
    seen: set[str] = set()
    for rule in rubric["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("rubric rule must be a mapping")
        rule_required = {
            "rule_id", "severity", "checker", "params", "summary", "evidence_paths", "recommendation"
        }
        rule_missing = sorted(rule_required - rule.keys())
        if rule_missing:
            raise ValueError(f"rubric rule missing fields: {', '.join(rule_missing)}")
        rule_id = rule["rule_id"]
        if not isinstance(rule_id, str) or not IDENTIFIER.fullmatch(rule_id) or rule_id in seen:
            raise ValueError(f"invalid or duplicate rule_id: {rule_id}")
        seen.add(rule_id)
        validate_severity(str(rule["severity"]))
        if rule["checker"] not in CHECKERS:
            raise ValueError(f"unregistered checker: {rule['checker']}")
        if not isinstance(rule["params"], dict):
            raise ValueError(f"{rule_id}: params must be a mapping")
        params = rule["params"]
        checker = rule["checker"]
        valid_params = False
        if checker in {"required_path", "non_empty"}:
            valid_params = isinstance(params.get("path"), str) and bool(params["path"])
        elif checker == "equals":
            valid_params = (
                isinstance(params.get("path"), str)
                and bool(params["path"])
                and "expected" in params
            )
        elif checker == "all_present":
            valid_params = (
                isinstance(params.get("paths"), list)
                and bool(params["paths"])
                and all(isinstance(path, str) and path for path in params["paths"])
            )
        elif checker == "hash_matches":
            valid_params = all(
                isinstance(params.get(key), str) and bool(params[key])
                for key in ("path", "expected_path")
            )
        elif checker == "covers_claims":
            valid_params = all(
                isinstance(params.get(key), str) and bool(params[key])
                for key in ("claims_path", "challenges_path", "claim_id_field")
            )
        if not valid_params:
            raise ValueError(f"{rule_id}: invalid checker params for {checker}")
        if not isinstance(rule["evidence_paths"], list) or not rule["evidence_paths"]:
            raise ValueError(f"{rule_id}: evidence_paths must be non-empty")
        if any(not isinstance(path, str) or not path for path in rule["evidence_paths"]):
            raise ValueError(f"{rule_id}: evidence_paths must contain strings")
        if not str(rule["summary"]).strip() or not str(rule["recommendation"]).strip():
            raise ValueError(f"{rule_id}: summary and recommendation must be non-empty")
    return rubric


def load_rubric(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load rubric {path}: {exc}") from exc
    return _validate_rubric(payload)


def _at_path(inputs: Mapping[str, object], path: str) -> object:
    current: object = inputs
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _non_empty(value: object) -> bool:
    if value is _MISSING or value is None:
        return False
    if isinstance(value, (str, list, tuple, dict, set)):
        return bool(value)
    return True


def _rule_passes(inputs: Mapping[str, object], checker: str, params: Mapping[str, object]) -> bool:
    if checker == "required_path":
        return _at_path(inputs, str(params.get("path", ""))) is not _MISSING
    if checker == "non_empty":
        return _non_empty(_at_path(inputs, str(params.get("path", ""))))
    if checker == "equals":
        return _at_path(inputs, str(params.get("path", ""))) == params.get("expected")
    if checker == "all_present":
        paths = params.get("paths")
        return isinstance(paths, list) and bool(paths) and all(
            isinstance(path, str) and _non_empty(_at_path(inputs, path)) for path in paths
        )
    if checker == "hash_matches":
        actual = _at_path(inputs, str(params.get("path", "")))
        expected = _at_path(inputs, str(params.get("expected_path", "")))
        return actual is not _MISSING and expected is not _MISSING and actual == expected
    if checker == "covers_claims":
        claims = _at_path(inputs, str(params.get("claims_path", "")))
        challenges = _at_path(inputs, str(params.get("challenges_path", "")))
        claim_id_field = params.get("claim_id_field")
        if (
            not isinstance(claims, list)
            or not claims
            or not isinstance(challenges, list)
            or not isinstance(claim_id_field, str)
        ):
            return False
        challenged = {
            item.get(claim_id_field)
            for item in challenges
            if isinstance(item, Mapping)
        }
        return all(isinstance(claim, str) and claim in challenged for claim in claims)
    raise ValueError(f"unregistered checker: {checker}")


def _evidence_for_rule(inputs: Mapping[str, object], paths: list[str]) -> list[str]:
    values: list[str] = []
    for path in paths:
        value = _at_path(inputs, path)
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, str) and CLAIM_ID.fullmatch(candidate):
                values.append(candidate)
    return sorted(set(values))


def _validate_evidence_index(
    inputs: Mapping[str, object], evidence_refs: Iterable[str]
) -> list[str]:
    evidence_index = inputs.get("evidence_index")
    if not isinstance(evidence_index, Mapping):
        return ["missing evidence_index for review evidence"]
    errors: list[str] = []
    for claim_id in sorted(set(evidence_refs)):
        record = evidence_index.get(claim_id)
        if not isinstance(record, Mapping) or record.get("claim_id") != claim_id:
            errors.append(f"unresolved evidence in evidence_index: {claim_id}")
    return errors


def _finding_validator() -> Draft202012Validator:
    repo_root = Path(__file__).resolve().parents[4]
    schema = json.loads(
        (repo_root / "shared/contracts/review-finding.schema.json").read_text(encoding="utf-8")
    )
    return make_validator(schema)


def _report_validator() -> Draft202012Validator:
    repo_root = Path(__file__).resolve().parents[4]
    contract_root = repo_root / "shared/contracts"
    finding_schema = json.loads(
        (contract_root / "review-finding.schema.json").read_text(encoding="utf-8")
    )
    report_schema = json.loads(
        (contract_root / "review-report.schema.json").read_text(encoding="utf-8")
    )
    registry = Registry().with_resource(
        finding_schema["$id"], Resource.from_contents(finding_schema)
    )
    return make_validator(report_schema, registry=registry)


def _snapshot_files(
    reviewed_files: Iterable[Path], file_root: Path | None
) -> list[dict[str, object]]:
    paths = list(reviewed_files)
    if not paths:
        return []
    if file_root is None:
        raise ValueError("file_root is required when reviewed_files are provided")
    root = file_root.resolve()
    snapshots: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"reviewed file escapes file_root: {path}") from exc
        if relative in seen:
            raise ValueError(f"duplicate reviewed file: {relative}")
        if not resolved.is_file():
            raise ValueError(f"reviewed file is missing or not a file: {relative}")
        seen.add(relative)
        content = resolved.read_bytes()
        snapshots.append(
            {
                "path": relative,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return sorted(snapshots, key=lambda item: str(item["path"]))


def review(
    inputs: dict[str, object],
    rubric: dict[str, object],
    *,
    capabilities: set[str] | None = None,
    reviewed_at: str | None = None,
    reviewed_files: Iterable[Path] = (),
    file_root: Path | None = None,
    score_dimensions: Iterable[Mapping[str, object]] | None = None,
    reviewer_findings: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    checked = _validate_rubric(rubric)
    rubric_digest = canonical_digest(checked)
    reviewed_file_manifest = _snapshot_files(reviewed_files, file_root)
    submitted_scores = None if score_dimensions is None else list(score_dimensions)
    submitted_findings = list(reviewer_findings)
    input_digest = canonical_digest(
        {
            "inputs": inputs,
            "reviewed_files": reviewed_file_manifest,
            "score_dimensions": submitted_scores,
            "reviewer_findings": submitted_findings,
        }
    )
    identity = canonical_digest(
        {
            "rubric_digest": rubric_digest,
            "input_digest": input_digest,
        }
    )
    timestamp = reviewed_at if reviewed_at is not None else utc_now_rfc3339()
    if not isinstance(timestamp, str) or not validate_rfc3339(timestamp):
        raise ValueError("reviewed_at must be an RFC 3339 date-time")
    errors: list[str] = []
    available = set(capabilities or set())
    missing_capabilities = sorted(set(checked["requires_capabilities"]) - available)
    if missing_capabilities:
        errors.append(f"missing required capabilities: {', '.join(missing_capabilities)}")
    root_evidence = _evidence_for_rule(inputs, ["evidence_refs"])
    if not root_evidence:
        errors.append("missing valid evidence_refs for review findings")
    errors.extend(_validate_evidence_index(inputs, root_evidence))

    scorecard: dict[str, object] | None = None
    if "scoring" in checked:
        if submitted_scores is None:
            errors.append("missing score dimensions for scored rubric")
        else:
            try:
                scorecard = evaluate_scorecard(checked, submitted_scores)
            except ValueError as exc:
                errors.append(f"invalid score dimensions: {exc}")
            if scorecard is not None:
                score_evidence = {
                    ref
                    for dimension in scorecard["dimensions"]
                    for ref in dimension["evidence_refs"]
                }
                if not score_evidence.issubset(root_evidence):
                    errors.append("score evidence refers to claims outside current inputs")
    elif submitted_scores is not None:
        errors.append("score dimensions supplied for unscored rubric")

    findings: list[dict[str, object]] = []
    validator = _finding_validator()
    if not errors:
        for rule in checked["rules"]:
            if _rule_passes(inputs, rule["checker"], rule["params"]):
                continue
            evidence_refs = _evidence_for_rule(inputs, rule["evidence_paths"])
            if not evidence_refs:
                errors.append(f"{rule['rule_id']}: no valid evidence reference")
                continue
            finding: dict[str, object] = {
                "schema_version": "1.0",
                "finding_id": f"finding_{rule['rule_id']}",
                "review_gate": checked["review_gate"],
                "severity": rule["severity"],
                "summary": rule["summary"],
                "evidence_refs": evidence_refs,
                "recommendation": rule["recommendation"],
                "status": "open",
            }
            validation_errors = sorted(validator.iter_errors(finding), key=lambda error: list(error.path))
            if validation_errors:
                raise ValueError(
                    f"generated finding violates contract: {validation_errors[0].message}"
                )
            findings.append(finding)

    seen_finding_ids = {str(finding["finding_id"]) for finding in findings}
    for candidate in submitted_findings:
        if not isinstance(candidate, Mapping):
            errors.append("reviewer finding must be a mapping")
            continue
        finding = dict(candidate)
        validation_errors = sorted(validator.iter_errors(finding), key=lambda error: list(error.path))
        if validation_errors:
            errors.append(f"invalid reviewer finding: {validation_errors[0].message}")
            continue
        finding_id = str(finding["finding_id"])
        if finding_id in seen_finding_ids:
            errors.append(f"duplicate finding_id: {finding_id}")
            continue
        if finding["review_gate"] != checked["review_gate"]:
            errors.append(f"{finding_id}: review_gate does not match rubric")
            continue
        if finding["status"] != "open":
            errors.append(f"{finding_id}: reviewer findings must have open status")
            continue
        if not set(finding["evidence_refs"]).issubset(root_evidence):
            errors.append(f"{finding_id}: finding refers to evidence outside current inputs")
            continue
        seen_finding_ids.add(finding_id)
        findings.append(finding)

    if scorecard is not None and not scorecard["passed"]:
        score_finding: dict[str, object] = {
            "schema_version": "1.0",
            "finding_id": f"finding_{checked['review_gate']}_score_threshold",
            "review_gate": checked["review_gate"],
            "severity": "S1",
            "summary": "The deterministic quality score did not meet the total or dimension threshold.",
            "evidence_refs": sorted(
                {
                    ref
                    for dimension in scorecard["dimensions"]
                    for ref in dimension["evidence_refs"]
                }
            ),
            "recommendation": "Revise the low-scoring dimensions and rerun the complete review.",
            "status": "open",
        }
        validation_errors = sorted(
            validator.iter_errors(score_finding), key=lambda error: list(error.path)
        )
        if validation_errors:
            raise ValueError(
                f"generated score finding violates contract: {validation_errors[0].message}"
            )
        if score_finding["finding_id"] in seen_finding_ids:
            errors.append(f"duplicate finding_id: {score_finding['finding_id']}")
        else:
            findings.append(score_finding)

    report: dict[str, object] = {
        "schema_version": "1.0",
        "review_id": f"review_{identity[:16]}",
        "rubric_id": checked["rubric_id"],
        "rubric_version": checked["version"],
        "review_gate": checked["review_gate"],
        "evaluated_rule_ids": [rule["rule_id"] for rule in checked["rules"]],
        "rubric_digest": rubric_digest,
        "input_digest": input_digest,
        "reviewed_files": reviewed_file_manifest,
        "status": gate_status(findings, errors),
        "scorecard": scorecard,
        "findings": findings,
        "errors": errors,
        "reviewed_at": timestamp,
    }
    validation_errors = sorted(
        _report_validator().iter_errors(report), key=lambda error: list(error.path)
    )
    if validation_errors:
        raise ValueError(f"generated review report violates contract: {validation_errors[0].message}")
    return report


def is_review_current(
    report: Mapping[str, object],
    inputs: dict[str, object],
    rubric: dict[str, object],
    *,
    reviewed_files: Iterable[Path] = (),
    file_root: Path | None = None,
    score_dimensions: Iterable[Mapping[str, object]] | None = None,
    reviewer_findings: Iterable[Mapping[str, object]] = (),
) -> bool:
    checked = _validate_rubric(rubric)
    reviewed_file_manifest = _snapshot_files(reviewed_files, file_root)
    submitted_scores = None if score_dimensions is None else list(score_dimensions)
    submitted_findings = list(reviewer_findings)
    current_input_digest = canonical_digest(
        {
            "inputs": inputs,
            "reviewed_files": reviewed_file_manifest,
            "score_dimensions": submitted_scores,
            "reviewer_findings": submitted_findings,
        }
    )
    return (
        report.get("input_digest") == current_input_digest
        and report.get("rubric_digest") == canonical_digest(checked)
    )
