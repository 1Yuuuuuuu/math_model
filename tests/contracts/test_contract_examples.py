import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts.contract_formats import FORMAT_CHECKER


def test_catalog_examples_match_their_schemas(project_root) -> None:
    catalog_path = project_root / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    for entry in catalog["contracts"]:
        schema = json.loads((project_root / entry["schema"]).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)

        for relative_path in entry["valid_examples"]:
            fixture = json.loads((project_root / relative_path).read_text(encoding="utf-8"))
            validator.validate(fixture)

        for relative_path in entry["invalid_examples"]:
            fixture = json.loads((project_root / relative_path).read_text(encoding="utf-8"))
            with pytest.raises(ValidationError):
                validator.validate(fixture)
