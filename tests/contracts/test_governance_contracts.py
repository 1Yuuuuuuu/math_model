import pytest
from jsonschema import Draft202012Validator, ValidationError

from conftest import FORMAT_CHECKER, load_json


CASES = [
    ("review-finding", "review-finding", "review-finding-bad-severity"),
    ("annual-rule", "annual-rule", "annual-rule-missing-source"),
    ("asset-manifest", "asset-manifest", "asset-manifest-duplicate-target"),
]


@pytest.mark.parametrize(("schema_name", "valid_name", "invalid_name"), CASES)
def test_valid_and_invalid_governance_contract_examples(
    project_root, schema_name, valid_name, invalid_name
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json")
        )
