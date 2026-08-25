import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.project.scaffold import scaffold_workspace


def write_template(root: Path) -> None:
    (root / "data").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "README.md").write_text("# workspace\n", encoding="utf-8")
    (root / "data" / "notes.txt").write_text("x", encoding="utf-8")


def test_scaffold_creates_exact_template_tree(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    result = scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    target = tmp_path / "ws_demo"
    assert (target / "README.md").read_text(encoding="utf-8") == "# workspace\n"
    assert (target / "data" / "notes.txt").read_text(encoding="utf-8") == "x"
    paths = {entry["path"] for entry in result["files"]}
    assert paths == {"README.md", "data/notes.txt"}
    assert result["workspace_id"] == "ws_demo"


def test_scaffold_refuses_to_overwrite_existing_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    with pytest.raises(FileExistsError):
        scaffold_workspace(tmp_path, "ws_demo", template_root=template)


def test_scaffold_refuses_target_with_only_subdirectory(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    (tmp_path / "ws_demo" / "user_only_dir").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        scaffold_workspace(tmp_path, "ws_demo", template_root=template)


def test_scaffold_overwrite_flag_replaces_template_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    (tmp_path / "ws_demo" / "README.md").write_text("changed", encoding="utf-8")
    scaffold_workspace(tmp_path, "ws_demo", template_root=template, overwrite=True)
    assert (tmp_path / "ws_demo" / "README.md").read_text(encoding="utf-8") == "# workspace\n"


def test_scaffold_missing_template_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scaffold_workspace(tmp_path, "ws_demo", template_root=tmp_path / "nope")


def test_scaffold_cli_reports_failure_json(tmp_path: Path, project_root: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.project.scaffold",
         "--target", str(tmp_path), "--workspace-id", "ws_demo"],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": str(project_root / "toolkit" / "src")},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", ".", "..", ""])
def test_scaffold_rejects_escaping_or_nested_workspace_id(tmp_path: Path, bad_id: str) -> None:
    template = tmp_path / "template"
    write_template(template)
    with pytest.raises(ValueError):
        scaffold_workspace(tmp_path, bad_id, template_root=template)


def test_scaffold_rejects_non_str_workspace_id(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    with pytest.raises(ValueError):
        scaffold_workspace(tmp_path, 12345, template_root=template)  # type: ignore[arg-type]


def test_scaffold_rejects_target_that_is_a_file(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    blocker = tmp_path / "ws_demo"
    blocker.write_text("occupied", encoding="utf-8")
    with pytest.raises(FileExistsError, match="as a file"):
        scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    with pytest.raises(FileExistsError, match="as a file"):
        scaffold_workspace(tmp_path, "ws_demo", template_root=template, overwrite=True)
