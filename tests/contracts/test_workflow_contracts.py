import pytest
from jsonschema import Draft202012Validator, ValidationError

from conftest import FORMAT_CHECKER, load_json


CASES = [
    ("evidence-link", "evidence-link", "evidence-link-missing-boundary"),
    ("decision", "decision", "decision-nonhuman"),
    ("workflow-state", "workflow-state", "workflow-state-skipped-gate"),
]


@pytest.mark.parametrize(("schema_name", "valid_name", "invalid_name"), CASES)
def test_valid_and_invalid_workflow_contract_examples(
    project_root, schema_name, valid_name, invalid_name
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json")
        )


def test_valid_workflow_has_exactly_the_four_human_gate_keys(project_root) -> None:
    workflow = load_json(project_root / "shared/fixtures/contracts/valid/workflow-state.json")
    assert set(workflow["gates"]) == {
        "gate_1_problem",
        "gate_2_model",
        "gate_3_outline",
        "gate_4_submission",
    }
