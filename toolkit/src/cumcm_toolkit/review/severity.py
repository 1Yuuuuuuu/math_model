from __future__ import annotations

from collections.abc import Iterable, Mapping


SEVERITIES = frozenset({"S0", "S1", "S2", "S3"})
FINDING_STATUSES = frozenset({"open", "resolved", "accepted_risk"})


def validate_severity(value: str) -> str:
    if value not in SEVERITIES:
        raise ValueError(f"invalid severity: {value}")
    return value


def is_blocking(severity: str, status: str = "open") -> bool:
    validate_severity(severity)
    if status not in FINDING_STATUSES:
        raise ValueError(f"invalid finding status: {status}")
    return status in {"open", "accepted_risk"} and severity in {"S0", "S1"}


def gate_status(findings: Iterable[Mapping[str, object]], errors: list[str]) -> str:
    if errors:
        return "blocked"
    for finding in findings:
        if is_blocking(str(finding.get("severity")), str(finding.get("status", "open"))):
            return "failed"
    return "passed"
