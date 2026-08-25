from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from cumcm_toolkit.experiments.manifest import utc_now_rfc3339
from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "citation-link.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)


def link_citation(
    *,
    citation_id: str,
    claim_id: str,
    source_id: str,
    usage: str,
    locator: dict[str, str],
    support_boundary: str,
    verified_at: str,
) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "1.0",
        "citation_id": citation_id,
        "claim_id": claim_id,
        "source_id": source_id,
        "usage": usage,
        "locator": dict(locator),
        "support_boundary": support_boundary,
        "verified_at": verified_at,
    }
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"citation link invalid: {errors[0].message}")
    return record


def link_approved_source(
    *,
    source_record: dict[str, Any],
    claim_id: str,
    usage: str,
    locator: dict[str, str],
    support_boundary: str,
) -> dict[str, object]:
    if source_record.get("verification_status") != "approved":
        raise ValueError("citation source must be approved")
    if not source_record.get("decision_id"):
        raise ValueError("approved source must carry a human decision_id")
    source_id = source_record.get("source_id")
    if source_id is None:
        # Fail closed with a clear error instead of a bare KeyError.
        raise ValueError("source record missing source_id")
    digest = hashlib.sha256(f"{source_id}\n{claim_id}\n{usage}".encode("utf-8")).hexdigest()
    return link_citation(
        citation_id=f"cite_{digest[:24]}",
        claim_id=claim_id,
        source_id=source_id,
        usage=usage,
        locator=locator,
        support_boundary=support_boundary,
        verified_at=utc_now_rfc3339(),
    )


def approved_sources(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("verification_status") == "approved" and record.get("decision_id")
    ]
