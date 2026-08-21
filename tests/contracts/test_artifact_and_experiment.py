from jsonschema import Draft202012Validator, ValidationError
import pytest

from conftest import FORMAT_CHECKER, load_json


@pytest.mark.parametrize(
    ("schema_name", "valid_name", "invalid_name"),
    [
        ("artifact", "artifact", "artifact-absolute-path"),
        ("experiment", "experiment", "experiment-missing-input"),
    ],
)
def test_valid_and_invalid_contract_examples(project_root, schema_name, valid_name, invalid_name) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json"))


def test_artifact_parent_traversal_example_is_invalid(project_root) -> None:
    schema = load_json(project_root / "shared/contracts/artifact.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / "shared/fixtures/contracts/invalid/artifact-parent-traversal.json")
        )


def test_experiment_timezone_less_example_is_invalid(project_root) -> None:
    schema = load_json(project_root / "shared/contracts/experiment.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / "shared/fixtures/contracts/invalid/experiment-timezone-less.json")
        )


def test_experiment_malformed_timestamp_requires_format_checker(project_root) -> None:
    schema = load_json(project_root / "shared/contracts/experiment.schema.json")
    invalid_experiment = load_json(project_root / "shared/fixtures/contracts/valid/experiment.json")
    invalid_experiment["started_at"] = "2026-13-10T09:00:00+08:00"
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(invalid_experiment)
