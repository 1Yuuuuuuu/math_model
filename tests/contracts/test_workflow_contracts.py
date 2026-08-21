from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from conftest import FORMAT_CHECKER, load_json


CASES = [
    ("evidence-link", "evidence-link", "evidence-link-missing-boundary"),
    ("decision", "decision", "decision-nonhuman"),
    ("workflow-state", "workflow-state", "workflow-state-skipped-gate"),
]

STAGE_VALID_GATES = {
    "intake": {
        "gate_1_problem": "pending",
        "gate_2_model": "pending",
        "gate_3_outline": "pending",
        "gate_4_submission": "pending",
    },
    "model_design": {
        "gate_1_problem": "approved",
        "gate_2_model": "pending",
        "gate_3_outline": "pending",
        "gate_4_submission": "pending",
    },
    "solve": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "pending",
        "gate_4_submission": "pending",
    },
    "outline": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "pending",
        "gate_4_submission": "pending",
    },
    "write": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "approved",
        "gate_4_submission": "pending",
    },
    "review": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "approved",
        "gate_4_submission": "pending",
    },
    "submission": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "approved",
        "gate_4_submission": "pending",
    },
    "complete": {
        "gate_1_problem": "approved",
        "gate_2_model": "approved",
        "gate_3_outline": "approved",
        "gate_4_submission": "approved",
    },
}

GATE_REJECTION_CASES = [
    (stage, "gate_1_problem", state)
    for stage in ("model_design", "solve", "outline", "write", "review", "submission", "complete")
    for state in ("pending", "rejected")
] + [
    (stage, "gate_2_model", state)
    for stage in ("solve", "outline", "write", "review", "submission", "complete")
    for state in ("pending", "rejected")
] + [
    (stage, "gate_3_outline", state)
    for stage in ("write", "review", "submission", "complete")
    for state in ("pending", "rejected")
] + [
    ("complete", "gate_4_submission", state) for state in ("pending", "rejected")
]

BOUNDARY_VALID_STAGES = ("intake", "model_design", "outline", "submission")


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


@pytest.mark.parametrize(("stage", "gate", "state"), GATE_REJECTION_CASES)
def test_later_stages_reject_unapproved_required_human_gates(project_root, stage, gate, state) -> None:
    schema = load_json(project_root / "shared/contracts/workflow-state.schema.json")
    workflow = load_json(project_root / "shared/fixtures/contracts/valid/workflow-state.json")
    workflow["stage"] = stage
    workflow["gates"] = deepcopy(STAGE_VALID_GATES[stage])
    workflow["gates"][gate] = state
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(workflow)


@pytest.mark.parametrize("stage", BOUNDARY_VALID_STAGES)
def test_human_gate_stage_boundaries_accept_the_expected_pending_gate(project_root, stage) -> None:
    schema = load_json(project_root / "shared/contracts/workflow-state.schema.json")
    workflow = load_json(project_root / "shared/fixtures/contracts/valid/workflow-state.json")
    workflow["stage"] = stage
    workflow["gates"] = deepcopy(STAGE_VALID_GATES[stage])
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(workflow)
