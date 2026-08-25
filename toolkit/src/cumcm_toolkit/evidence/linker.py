from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "evidence-link.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _validate(record: dict[str, Any]) -> dict[str, Any]:
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"evidence link invalid: {errors[0].message}")
    return record


def link_claim(
    *,
    claim_id: str,
    claim_text: str,
    artifact_id: str,
    experiment_id: str,
    locator: dict[str, str],
    boundary: str,
) -> dict[str, object]:
    return _validate(
        {
            "schema_version": "1.0",
            "claim_id": claim_id,
            "claim_text": claim_text,
            "artifact_id": artifact_id,
            "experiment_id": experiment_id,
            "locator": dict(locator),
            "boundary": boundary,
        }
    )


def link_claim_to_metrics(
    claim_id: str,
    claim_text: str,
    experiment_record: dict[str, Any],
    metric_keys: list[str],
    boundary: str,
) -> dict[str, object]:
    metrics = experiment_record.get("metrics", {})
    present = [key for key in metric_keys if key in metrics]
    if not present:
        raise ValueError("no requested metric keys present in experiment record")
    for key in present:
        value = metrics[key]
        if str(value) in claim_text:
            artifact_id = experiment_record.get("output_artifact_ids") or ["art_unknown"]
            return link_claim(
                claim_id=claim_id,
                claim_text=claim_text,
                artifact_id=artifact_id[0],
                experiment_id=experiment_record["experiment_id"],
                locator={"kind": "metric", "value": key},
                boundary=boundary,
            )
    raise ValueError(f"claim text does not contain any metric value from {present}")


def resolve_numeric_claims(abstract_text: str, links: list[dict[str, Any]]) -> dict[str, object]:
    numbers = _NUMBER.findall(abstract_text)
    claims: list[dict[str, object]] = []
    unresolved: list[object] = []
    for number in numbers:
        matched = False
        for link in links:
            text = link.get("claim_text", "")
            metrics = link.get("metrics", {})
            if number in text or any(number == str(v) for v in metrics.values()):
                matched = True
                claims.append({"claim_id": link.get("claim_id"), "number": number, "in_abstract": True, "in_evidence": True})
                break
        if not matched:
            unresolved.append({"number": number})
    return {
        "status": "ok" if not unresolved else "failed",
        "claims": claims,
        "unresolved": unresolved,
    }
