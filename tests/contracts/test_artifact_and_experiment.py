from jsonschema import Draft202012Validator, ValidationError
import pytest

from conftest import load_json


@pytest.mark.parametrize(
    ("schema_name", "valid_name", "invalid_name"),
    [
        ("artifact", "artifact", "artifact-absolute-path"),
        ("experiment", "experiment", "experiment-missing-input"),
    ],
)
def test_valid_and_invalid_contract_examples(project_root, schema_name, valid_name, invalid_name) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json"))
