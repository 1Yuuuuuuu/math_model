import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.latex.scaffold import scaffold_paper


def write_template(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.tex").write_text("\\documentclass{ctexart}\n", encoding="utf-8")
    (root / "cumcm.sty").write_text("% style\n", encoding="utf-8")
    (root / "bibliography.bib").write_text("% bib\n", encoding="utf-8")


def test_scaffold_creates_template_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    result = scaffold_paper(tmp_path, "paper2026", template_root=template)
    target = tmp_path / "paper2026"
    assert (target / "main.tex").is_file()
    assert (target / "cumcm.sty").is_file()
    assert (target / "bibliography.bib").is_file()
    paths = {entry["path"] for entry in result["files"]}
    assert paths == {"main.tex", "cumcm.sty", "bibliography.bib"}
    assert result["paper_id"] == "paper2026"


def test_scaffold_refuses_overwrite(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_paper(tmp_path, "paper2026", template_root=template)
    with pytest.raises(FileExistsError):
        scaffold_paper(tmp_path, "paper2026", template_root=template)


def test_scaffold_rejects_invalid_paper_id(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    for bad_id in ["../evil", "a/b", ".", "..", ""]:
        with pytest.raises(ValueError):
            scaffold_paper(tmp_path, bad_id, template_root=template)


def test_scaffold_missing_template_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scaffold_paper(tmp_path, "paper2026", template_root=tmp_path / "nope")


def test_scaffold_cli_reports_failure_json(tmp_path: Path, project_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.latex.scaffold",
         "--target", str(tmp_path), "--paper-id", "../evil"],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": str(project_root / "toolkit" / "src") + os.pathsep + str(project_root)},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
