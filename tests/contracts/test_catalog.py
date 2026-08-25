import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts.validate_contracts import make_validator
from tests.contracts.conftest import FORMAT_CHECKER, load_json


EXPECTED_CONTRACT_IDS = {
    "error",
    "artifact",
    "experiment",
    "evidence-link",
    "decision",
    "workflow-state",
    "review-finding",
    "annual-rule",
    "asset-manifest",
    "literature-source",
    "citation-link",
    "modeling-handoff",
    "review-report",
    "review-bundle",
    "workflow-event",
}


def test_catalog_paths_and_schemas_are_valid(project_root) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    assert catalog["catalog_version"] == "1.0"
    ids = [entry["id"] for entry in catalog["contracts"]]
    assert set(ids) == EXPECTED_CONTRACT_IDS
    assert len(ids) == 15
    assert len(ids) == len(set(ids))
    for entry in catalog["contracts"]:
        schema_path = project_root / entry["schema"]
        assert schema_path.is_file()
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        validator = make_validator(schema)
        assert entry["valid_examples"]
        assert entry["invalid_examples"]
        assert all((project_root / path).is_file() for path in entry["valid_examples"])
        assert all((project_root / path).is_file() for path in entry["invalid_examples"])
        for path in entry["valid_examples"]:
            validator.validate(load_json(project_root / path))
        for path in entry["invalid_examples"]:
            with pytest.raises(ValidationError):
                validator.validate(load_json(project_root / path))
