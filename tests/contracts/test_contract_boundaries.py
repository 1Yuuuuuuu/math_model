from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts import contract_formats
from scripts.validate_contracts import load_json, make_validator, resolve_catalog_path


PATTERN_FIELD_CASES = (
    ("annual-rule", ("rule_set_id",)),
    ("annual-rule", ("items", 0, "rule_id")),
    ("artifact", ("artifact_id",)),
    ("artifact", ("path",)),
    ("artifact", ("sha256",)),
    ("artifact", ("source_artifact_ids", 0)),
    ("asset-manifest", ("assets", 0, "asset_id")),
    ("asset-manifest", ("assets", 0, "source_path")),
    ("asset-manifest", ("assets", 0, "sha256")),
    ("citation-link", ("citation_id",)),
    ("citation-link", ("claim_id",)),
    ("citation-link", ("source_id",)),
    ("citation-link", ("locator", "value")),
    ("decision", ("decision_id",)),
    ("decision", ("artifact_ids", 0)),
    ("error", ("code",)),
    ("evidence-link", ("claim_id",)),
    ("evidence-link", ("artifact_id",)),
    ("evidence-link", ("experiment_id",)),
    ("evidence-link", ("locator", "value")),
    ("experiment", ("experiment_id",)),
    ("experiment", ("input_artifact_ids", 0)),
    ("experiment", ("code_artifact_id",)),
    ("experiment", ("environment", "lock_sha256")),
    ("experiment", ("output_artifact_ids", 0)),
    ("literature-source", ("source_id",)),
    ("literature-source", ("artifact_ids", 0)),
    ("literature-source", ("content_sha256",)),
    ("literature-source", ("decision_id",)),
    ("review-finding", ("finding_id",)),
    ("review-finding", ("evidence_refs", 0)),
    ("workflow-state", ("workspace_id",)),
    ("workflow-state", ("latest_artifact_ids", 0)),
)

INVALID_PORTABLE_PATHS = (
    "",
    "/absolute/file.txt",
    "C:/drive/file.txt",
    "C:\\drive\\file.txt",
    "folder\\file.txt",
    "../secret.txt",
    "folder/../secret.txt",
    "folder/./file.txt",
    "folder//file.txt",
    "folder/NUL",
    "folder/con.txt",
    "folder/COM1.log",
    "folder/Lpt9",
    "folder/COM¹",
    "COM².txt",
    "COM³.tar.gz",
    "LPT¹",
    "LPT².log",
    "LPT³.tar.gz",
    "folder/a:b.txt",
    "folder/question?.txt",
    "folder/star*.txt",
    "folder/pipe|.txt",
    "folder/angle<.txt",
    'folder/quote".txt',
    "folder/trailing.",
    "folder/trailing ",
    "folder/control\x00.txt",
    "folder/control\x7f.txt",
    "folder/control\x80.txt",
)

OBVIOUS_INVALID_PORTABLE_PATHS = tuple(
    path
    for path in INVALID_PORTABLE_PATHS
    if path
    not in {
        "folder/NUL",
        "folder/con.txt",
        "folder/COM1.log",
        "folder/Lpt9",
        "folder/COM¹",
        "COM².txt",
        "COM³.tar.gz",
        "LPT¹",
        "LPT².log",
        "LPT³.tar.gz",
    }
)

VALID_PORTABLE_PATHS = (
    "data/input.csv",
    "docs/model card.md",
    "nested/auxiliary.txt",
    "results/com10-value.txt",
)


def _patterns(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "pattern":
                yield child
            yield from _patterns(child)
    elif isinstance(value, list):
        for child in value:
            yield from _patterns(child)


def _replace_at_path(value: object, path: tuple[object, ...], replacement: str) -> None:
    current = value
    for segment in path[:-1]:
        current = current[segment]
    current[path[-1]] = replacement


def _value_at_path(value: object, path: tuple[object, ...]) -> str:
    current = value
    for segment in path:
        current = current[segment]
    assert isinstance(current, str)
    return current


def test_every_schema_pattern_uses_a_true_cross_runtime_end_assertion(project_root: Path) -> None:
    patterns = []
    for schema_path in sorted((project_root / "shared/contracts").glob("*.schema.json")):
        patterns.extend(_patterns(load_json(schema_path)))

    assert patterns
    assert all(not pattern.endswith("$") for pattern in patterns)
    assert all(pattern.endswith(r"(?![\s\S])") for pattern in patterns)


@pytest.mark.parametrize(("schema_name", "field_path"), PATTERN_FIELD_CASES)
@pytest.mark.parametrize("suffix", ("\n", "\r"), ids=("LF", "CR"))
def test_pattern_fields_reject_trailing_line_breaks(
    project_root: Path, schema_name: str, field_path: tuple[object, ...], suffix: str
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    fixture = deepcopy(
        load_json(project_root / f"shared/fixtures/contracts/valid/{schema_name}.json")
    )
    if field_path == ("source_artifact_ids", 0):
        fixture["source_artifact_ids"].append("art_seed")
    _replace_at_path(fixture, field_path, _value_at_path(fixture, field_path) + suffix)

    with pytest.raises(ValidationError):
        make_validator(schema).validate(fixture)


def test_strict_json_loader_rejects_nonstandard_constants(tmp_path: Path) -> None:
    path = tmp_path / "nonstandard.json"
    path.write_text('{"value": NaN}', encoding="utf-8")

    with pytest.raises(json.JSONDecodeError, match="non-standard JSON constant"):
        load_json(path)


def test_workspace_path_predicate_has_portable_cross_platform_boundaries() -> None:
    predicate = getattr(contract_formats, "is_cumcm_workspace_path", None)
    assert predicate is not None

    for path in VALID_PORTABLE_PATHS:
        assert predicate(path), path
    for path in INVALID_PORTABLE_PATHS:
        assert not predicate(path), path
    assert not predicate(None)


@pytest.mark.parametrize(
    ("schema_name", "field_path"),
    (
        ("artifact", ("path",)),
        ("asset-manifest", ("assets", 0, "source_path")),
    ),
)
@pytest.mark.parametrize("invalid_path", INVALID_PORTABLE_PATHS)
def test_contract_workspace_paths_reject_nonportable_names(
    project_root: Path,
    schema_name: str,
    field_path: tuple[object, ...],
    invalid_path: str,
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    fixture = deepcopy(
        load_json(project_root / f"shared/fixtures/contracts/valid/{schema_name}.json")
    )
    _replace_at_path(fixture, field_path, invalid_path)

    with pytest.raises(ValidationError):
        make_validator(schema).validate(fixture)


@pytest.mark.parametrize(
    ("schema_name", "field_path"),
    (
        ("artifact", ("path",)),
        ("asset-manifest", ("assets", 0, "source_path")),
    ),
)
@pytest.mark.parametrize("invalid_path", OBVIOUS_INVALID_PORTABLE_PATHS)
def test_basic_schema_patterns_reject_obvious_path_hazards_without_custom_formats(
    project_root: Path,
    schema_name: str,
    field_path: tuple[object, ...],
    invalid_path: str,
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    fixture = deepcopy(
        load_json(project_root / f"shared/fixtures/contracts/valid/{schema_name}.json")
    )
    _replace_at_path(fixture, field_path, invalid_path)

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(fixture)


@pytest.mark.parametrize("valid_path", VALID_PORTABLE_PATHS)
def test_contract_and_catalog_workspace_paths_accept_portable_names(
    project_root: Path, valid_path: str
) -> None:
    for schema_name, field_path in (
        ("artifact", ("path",)),
        ("asset-manifest", ("assets", 0, "source_path")),
    ):
        schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
        fixture = deepcopy(
            load_json(project_root / f"shared/fixtures/contracts/valid/{schema_name}.json")
        )
        _replace_at_path(fixture, field_path, valid_path)
        make_validator(schema).validate(fixture)

    assert resolve_catalog_path(project_root, valid_path) == (project_root / valid_path).resolve()


@pytest.mark.parametrize("invalid_path", INVALID_PORTABLE_PATHS)
def test_catalog_workspace_paths_reject_nonportable_names(
    project_root: Path, invalid_path: str
) -> None:
    with pytest.raises(ValueError, match="catalog path"):
        resolve_catalog_path(project_root, invalid_path)
