import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

import json
import math
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validators
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.contract_formats import FORMAT_CHECKER, is_cumcm_workspace_path


CONTRACT_ID = re.compile(r"[a-z][a-z0-9_-]*\Z")
READ_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError)
VALIDATION_ERRORS = (SchemaError, ValidationError, Unresolvable)


def _is_finite_json_number(checker: object, instance: object) -> bool:
    return (
        isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and (not isinstance(instance, float) or math.isfinite(instance))
    )


OfflineDraft202012Validator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "number", _is_finite_json_number
    ),
)


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonstandard_json_constant,
    )


def build_offline_registry(root: Path) -> Registry:
    registry = Registry()
    for path in sorted((root / "shared/contracts").glob("*.schema.json")):
        try:
            schema = load_json(path)
        except READ_ERRORS:
            continue
        schema_id = schema.get("$id") if isinstance(schema, dict) else None
        if not isinstance(schema_id, str) or not schema_id:
            continue
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


OFFLINE_REGISTRY = build_offline_registry(ROOT)


def resolve_catalog_path(root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("catalog path must be a non-empty workspace-relative string")
    candidate_path = Path(relative_path)
    portable = is_cumcm_workspace_path(relative_path)
    if not portable and (
        "\\" in relative_path
        or relative_path.startswith("/")
        or candidate_path.is_absolute()
        or candidate_path.drive
        or re.match(r"[A-Za-z]:", relative_path)
    ):
        raise ValueError(f"catalog path must be workspace-relative: {relative_path}")
    if not portable and ".." in relative_path.split("/"):
        raise ValueError(f"catalog path escapes workspace: {relative_path}")
    if not portable:
        raise ValueError(f"catalog path must be portable: {relative_path}")

    resolved_root = root.resolve()
    resolved_path = (root / candidate_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"catalog path escapes workspace: {relative_path}") from exc
    return resolved_path


def make_validator(
    schema: Any, *, registry: Registry | None = None
) -> Draft202012Validator:
    return OfflineDraft202012Validator(
        schema,
        format_checker=FORMAT_CHECKER,
        registry=OFFLINE_REGISTRY if registry is None else registry,
    )


def validate_catalog_shape(root: Path, entries: list[Any]) -> list[str]:
    errors: list[str] = []
    required_fields = ("id", "schema", "valid_examples", "invalid_examples")

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"catalog: contract entry at index {index} must be an object")
            continue

        contract_id = entry.get("id")
        if not isinstance(contract_id, str) or not CONTRACT_ID.fullmatch(contract_id):
            errors.append(
                f"catalog: contract entry at index {index} id must be a non-empty lowercase ASCII identifier"
            )
            continue

        missing = [field for field in required_fields if field not in entry]
        if missing:
            errors.append(f"{contract_id}: missing required catalog fields: {', '.join(missing)}")
            continue

        if not isinstance(entry["schema"], str) or not entry["schema"]:
            errors.append(f"{contract_id}: schema must be a non-empty workspace-relative string")
            continue

        invalid_example_field = next(
            (
                field
                for field in ("valid_examples", "invalid_examples")
                if not isinstance(entry[field], list) or not entry[field]
            ),
            None,
        )
        if invalid_example_field is not None:
            errors.append(
                f"{contract_id}: {invalid_example_field} must be a non-empty list of workspace-relative strings"
            )
            continue

        non_string_example_field = next(
            (
                field
                for field in ("valid_examples", "invalid_examples")
                if any(not isinstance(path, str) or not path for path in entry[field])
            ),
            None,
        )
        if non_string_example_field is not None:
            errors.append(
                f"{contract_id}: {non_string_example_field} must contain only non-empty workspace-relative strings"
            )
            continue

        try:
            resolve_catalog_path(root, entry["schema"])
            for field in ("valid_examples", "invalid_examples"):
                for relative_path in entry[field]:
                    resolve_catalog_path(root, relative_path)
        except ValueError as exc:
            errors.append(f"{contract_id}: {exc}")

    return sorted(errors)


def validate_catalog(root: Path) -> tuple[list[str], int]:
    catalog_path = root / "shared/contracts/catalog.json"
    try:
        catalog = load_json(catalog_path)
    except READ_ERRORS as exc:
        return [f"catalog: {exc}"], 0

    if not isinstance(catalog, dict):
        return ["catalog: top-level value must be an object"], 0
    if catalog.get("catalog_version") != "1.0":
        return ["catalog: catalog_version must be the string 1.0"], 0
    if "contracts" not in catalog:
        return ["catalog: missing required property: contracts"], 0
    entries = catalog["contracts"]
    if not isinstance(entries, list) or not entries:
        return ["catalog: contracts must be a non-empty list"], 0

    shape_errors = validate_catalog_shape(root, entries)
    if shape_errors:
        return shape_errors, len(entries)

    typed_entries: list[dict[str, Any]] = entries
    ids = [entry["id"] for entry in typed_entries]
    errors: list[str] = []
    if len(ids) != len(set(ids)):
        errors.append("catalog: duplicate contract id")

    for entry in typed_entries:
        contract_id = entry["id"]
        try:
            schema = load_json(resolve_catalog_path(root, entry["schema"]))
            Draft202012Validator.check_schema(schema)
            validator = make_validator(schema)

            for relative_path in entry["valid_examples"]:
                fixture = load_json(resolve_catalog_path(root, relative_path))
                try:
                    validator.validate(fixture)
                except ValidationError as exc:
                    errors.append(f"{contract_id}: valid fixture failed: {relative_path}: {exc.message}")

            for relative_path in entry["invalid_examples"]:
                fixture = load_json(resolve_catalog_path(root, relative_path))
                try:
                    validator.validate(fixture)
                except ValidationError:
                    continue
                errors.append(f"{contract_id}: invalid fixture passed: {relative_path}")
        except READ_ERRORS + VALIDATION_ERRORS + (ValueError,) as exc:
            errors.append(f"{contract_id}: {exc}")

    return sorted(errors), len(entries)


def main() -> int:
    errors, contract_count = validate_catalog(ROOT)
    payload = {
        "status": "ok" if not errors else "failed",
        "contracts": contract_count,
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
