from pathlib import Path

import pytest

from cumcm_toolkit.artifacts.index import index_artifacts
from cumcm_toolkit.project.scaffold import DEFAULT_TEMPLATE, scaffold_workspace
from scripts.validate_contracts import load_json, make_validator


def test_fresh_workspace_end_to_end(project_root: Path, tmp_path: Path) -> None:
    result = scaffold_workspace(tmp_path, "ws_2026", template_root=DEFAULT_TEMPLATE)
    target = tmp_path / "ws_2026"
    assert (target / "README.md").is_file()
    for directory in ("data", "code", "experiments", "artifacts", "paper"):
        assert (target / directory).is_dir()

    records = index_artifacts(target)
    schema = load_json(project_root / "shared/contracts/artifact.schema.json")
    validator = make_validator(schema)
    assert records, "expected at least README.md to be indexed"
    for record in records:
        assert list(validator.iter_errors(record)) == []
        assert record["path"] not in ("data/.gitkeep", "code/.gitkeep")

    with pytest.raises(FileExistsError):
        scaffold_workspace(tmp_path, "ws_2026", template_root=DEFAULT_TEMPLATE)
