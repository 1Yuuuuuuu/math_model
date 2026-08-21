import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.contract_formats import FORMAT_CHECKER


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_catalog_path(root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("catalog path must be a non-empty workspace-relative string")
    candidate_path = Path(relative_path)
    if "\\" in relative_path or candidate_path.is_absolute() or candidate_path.drive:
        raise ValueError(f"catalog path must be workspace-relative: {relative_path}")

    resolved_root = root.resolve()
    resolved_path = (root / candidate_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"catalog path escapes workspace: {relative_path}") from exc
    return resolved_path


def validate_catalog(root: Path) -> tuple[list[str], int]:
    catalog_path = root / "shared/contracts/catalog.json"
    try:
        catalog = load_json(catalog_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"catalog: {exc}"], 0

    if not isinstance(catalog, dict):
        return ["catalog: top-level value must be an object"], 0
    entries = catalog.get("contracts", [])
    if not isinstance(entries, list):
        return ["catalog: contracts must be a list"], 0

    errors: list[str] = []
    ids = [entry.get("id") if isinstance(entry, dict) else None for entry in entries]
    if len(ids) != len(set(ids)):
        errors.append("catalog: duplicate contract id")

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("catalog: contract entry must be an object")
            continue

        contract_id = str(entry.get("id", "<missing-id>"))
        try:
            schema_path = resolve_catalog_path(root, entry["schema"])
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)

            valid_examples = entry["valid_examples"]
            invalid_examples = entry["invalid_examples"]
            if not isinstance(valid_examples, list) or not isinstance(invalid_examples, list):
                raise ValueError("catalog example paths must be lists")

            for relative_path in valid_examples:
                fixture = load_json(resolve_catalog_path(root, relative_path))
                try:
                    validator.validate(fixture)
                except ValidationError as exc:
                    errors.append(f"{contract_id}: valid fixture failed: {relative_path}: {exc.message}")

            for relative_path in invalid_examples:
                fixture = load_json(resolve_catalog_path(root, relative_path))
                try:
                    validator.validate(fixture)
                except ValidationError:
                    continue
                errors.append(f"{contract_id}: invalid fixture passed: {relative_path}")
        except (KeyError, OSError, json.JSONDecodeError, SchemaError, ValueError) as exc:
            errors.append(f"{contract_id}: {exc}")

    return sorted(errors), len(entries)


def main() -> int:
    errors, contract_count = validate_catalog(ROOT)
    payload = {
        "status": "ok" if not errors else "failed",
        "contracts": contract_count,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
