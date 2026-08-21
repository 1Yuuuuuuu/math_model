from pathlib import Path

from scripts.validate_contracts import load_json, make_validator


def test_citation_link_requires_source_locator(project_root: Path) -> None:
    schema = load_json(project_root / "shared/contracts/citation-link.schema.json")
    validator = make_validator(schema)
    valid = load_json(project_root / "shared/fixtures/contracts/valid/citation-link.json")
    invalid = load_json(
        project_root
        / "shared/fixtures/contracts/invalid/citation-link-missing-locator.json"
    )

    assert list(validator.iter_errors(valid)) == []
    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == ()
    assert errors[0].validator == "required"
