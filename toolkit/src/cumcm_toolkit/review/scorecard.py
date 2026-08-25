from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any


DIMENSION_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
CLAIM_ID = re.compile(r"clm_[a-z0-9][a-z0-9_-]{2,63}\Z")


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def validate_scoring_definition(scoring: object) -> dict[str, Any]:
    if not isinstance(scoring, dict):
        raise ValueError("scoring must be a mapping")
    required = {"threshold", "dimension_floor", "dimensions"}
    missing = sorted(required - scoring.keys())
    if missing:
        raise ValueError(f"scoring missing fields: {', '.join(missing)}")

    threshold = _finite_number(scoring["threshold"], "threshold")
    dimension_floor = _finite_number(scoring["dimension_floor"], "dimension_floor")
    if not 0 <= threshold <= 100 or not 0 <= dimension_floor <= 100:
        raise ValueError("threshold and dimension_floor must be between 0 and 100")

    dimensions = scoring["dimensions"]
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("scoring dimensions must be a non-empty list")
    seen: set[str] = set()
    total_weight = 0.0
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            raise ValueError("scoring dimension must be a mapping")
        if set(dimension) != {"dimension_id", "weight", "summary"}:
            raise ValueError("scoring dimension fields must be dimension_id, weight, and summary")
        dimension_id = dimension["dimension_id"]
        if (
            not isinstance(dimension_id, str)
            or not DIMENSION_ID.fullmatch(dimension_id)
            or dimension_id in seen
        ):
            raise ValueError(f"invalid or duplicate scoring dimension: {dimension_id}")
        seen.add(dimension_id)
        weight = _finite_number(dimension["weight"], "dimension weight")
        if weight <= 0:
            raise ValueError("dimension weights must be positive")
        total_weight += weight
        if not isinstance(dimension["summary"], str) or not dimension["summary"].strip():
            raise ValueError(f"{dimension_id}: summary must be non-empty")
    if not math.isclose(total_weight, 100.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("dimension weights must sum to 100")
    return scoring


def evaluate_scorecard(
    rubric: Mapping[str, object], submitted_dimensions: Iterable[Mapping[str, object]]
) -> dict[str, object]:
    scoring = validate_scoring_definition(rubric.get("scoring"))
    submitted = list(submitted_dimensions)
    expected = [item["dimension_id"] for item in scoring["dimensions"]]
    received: dict[str, Mapping[str, object]] = {}
    for item in submitted:
        if not isinstance(item, Mapping):
            raise ValueError("submitted dimension must be a mapping")
        dimension_id = item.get("dimension_id")
        if not isinstance(dimension_id, str) or dimension_id in received:
            raise ValueError(f"invalid or duplicate submitted dimension: {dimension_id}")
        received[dimension_id] = item
    if set(received) != set(expected):
        raise ValueError("submitted dimension identities do not match rubric dimensions")

    evaluated: list[dict[str, object]] = []
    weighted_total = 0.0
    for definition in scoring["dimensions"]:
        dimension_id = definition["dimension_id"]
        item = received[dimension_id]
        score = _finite_number(item.get("score"), "score")
        if not 0 <= score <= 100:
            raise ValueError("score must be between 0 and 100")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"{dimension_id}: rationale must be non-empty")
        evidence_refs = item.get("evidence_refs")
        if (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or any(not isinstance(ref, str) or not CLAIM_ID.fullmatch(ref) for ref in evidence_refs)
            or len(evidence_refs) != len(set(evidence_refs))
        ):
            raise ValueError(f"{dimension_id}: evidence_refs must contain unique claim IDs")
        weight = float(definition["weight"])
        weighted_points = score * weight / 100.0
        weighted_total += weighted_points
        evaluated.append(
            {
                "dimension_id": dimension_id,
                "weight": definition["weight"],
                "score": score,
                "weighted_points": round(weighted_points, 10),
                "rationale": rationale.strip(),
                "evidence_refs": list(evidence_refs),
            }
        )
    weighted_total = round(weighted_total, 10)
    return {
        "threshold": scoring["threshold"],
        "dimension_floor": scoring["dimension_floor"],
        "weighted_total": weighted_total,
        "dimensions": evaluated,
        "passed": weighted_total >= float(scoring["threshold"])
        and all(item["score"] >= float(scoring["dimension_floor"]) for item in evaluated),
    }
