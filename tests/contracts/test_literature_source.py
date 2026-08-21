from pathlib import Path

from scripts.validate_contracts import load_json, make_validator


def test_approved_literature_source_requires_human_decision(project_root: Path) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    valid = load_json(project_root / "shared/fixtures/contracts/valid/literature-source.json")
    invalid = load_json(
        project_root
        / "shared/fixtures/contracts/invalid/literature-source-approved-without-decision.json"
    )

    assert list(validator.iter_errors(valid)) == []
    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == ()
    assert errors[0].validator == "required"
