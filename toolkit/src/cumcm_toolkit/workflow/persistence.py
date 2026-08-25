from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from cumcm_toolkit.review.engine import canonical_digest
from cumcm_toolkit.workflow.state import replay_workflow


MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024


def _records(values: Iterable[Mapping[str, object]], field: str) -> list[dict[str, object]]:
    try:
        copied = json.loads(
            json.dumps(
                [dict(value) for value in values],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must contain finite JSON objects: {exc}") from exc
    if not isinstance(copied, list) or any(not isinstance(item, dict) for item in copied):
        raise ValueError(f"{field} must be a list of objects")
    return copied


def save_workflow_checkpoint(
    path: Path,
    *,
    events: Iterable[Mapping[str, object]],
    decisions: Iterable[Mapping[str, object]],
    review_bundles: Iterable[Mapping[str, object]],
) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {
        "schema_version": "1.0",
        "events": _records(events, "events"),
        "decisions": _records(decisions, "decisions"),
        "review_bundles": _records(review_bundles, "review_bundles"),
    }
    # Validate the full replay before replacing the last known-good checkpoint.
    replay_workflow(
        body["events"],  # type: ignore[arg-type]
        decisions=body["decisions"],  # type: ignore[arg-type]
        review_bundles=body["review_bundles"],  # type: ignore[arg-type]
    )
    payload = {**body, "payload_digest": canonical_digest(body)}
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError("workflow checkpoint exceeds the size limit")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def load_workflow_checkpoint(path: Path) -> dict[str, object]:
    target = path.resolve()
    try:
        if target.stat().st_size > MAX_CHECKPOINT_BYTES:
            raise ValueError("workflow checkpoint exceeds the size limit")
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load workflow checkpoint: {exc}") from exc
    expected_fields = {
        "schema_version", "events", "decisions", "review_bundles", "payload_digest"
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("workflow checkpoint has invalid fields")
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported workflow checkpoint schema_version")
    digest = payload.pop("payload_digest")
    if not isinstance(digest, str) or canonical_digest(payload) != digest:
        raise ValueError("workflow checkpoint payload digest mismatch")
    for field in ("events", "decisions", "review_bundles"):
        if not isinstance(payload.get(field), list) or any(
            not isinstance(item, dict) for item in payload[field]
        ):
            raise ValueError(f"workflow checkpoint {field} must be a list of objects")
    payload["payload_digest"] = digest
    return payload


def replay_workflow_checkpoint(path: Path) -> dict[str, object]:
    payload = load_workflow_checkpoint(path)
    return replay_workflow(
        payload["events"],  # type: ignore[arg-type]
        decisions=payload["decisions"],  # type: ignore[arg-type]
        review_bundles=payload["review_bundles"],  # type: ignore[arg-type]
    )
