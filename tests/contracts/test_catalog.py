from jsonschema import Draft202012Validator

from conftest import load_json


def test_catalog_paths_and_schemas_are_valid(project_root) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    assert catalog["catalog_version"] == "1.0"
    ids = [entry["id"] for entry in catalog["contracts"]]
    assert len(ids) == len(set(ids))
    for entry in catalog["contracts"]:
        schema_path = project_root / entry["schema"]
        assert schema_path.is_file()
        Draft202012Validator.check_schema(load_json(schema_path))
        for key in ("valid_examples", "invalid_examples"):
            assert entry[key]
            assert all((project_root / path).is_file() for path in entry[key])
