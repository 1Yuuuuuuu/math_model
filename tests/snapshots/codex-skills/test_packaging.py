from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.package_codex_skills import (
    load_skill_catalog,
    package_skills,
    validate_resource_path,
    verify_packaged_output,
)


ROOT = Path(__file__).resolve().parents[3]


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.mark.parametrize("unsafe", ["../secret.txt", "/absolute/file", "C:/secret.txt"])
def test_resource_paths_cannot_escape_repository(unsafe: str) -> None:
    with pytest.raises(ValueError, match="unsafe resource path"):
        validate_resource_path(unsafe)


def test_skill_catalog_matches_source_directories() -> None:
    catalog = load_skill_catalog(ROOT)
    source_dirs = {
        path.name
        for path in (ROOT / "adapters/codex/skills").iterdir()
        if path.is_dir()
    }
    assert set(catalog) == source_dirs
    assert len(catalog) == len(set(catalog))


def test_packaging_rejects_existing_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="output directory already exists"):
        package_skills(ROOT, output)


def test_packaging_is_self_contained_hashed_and_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    package_skills(ROOT, first)
    package_skills(ROOT, second)
    assert _tree_hash(first) == _tree_hash(second)

    for skill_dir in sorted(first.iterdir()):
        manifest = json.loads((skill_dir / "asset-manifest.json").read_text(encoding="utf-8"))
        assert manifest["skill"] == skill_dir.name
        assert manifest["assets"]
        for asset in manifest["assets"]:
            packaged = skill_dir / asset["packaged_path"]
            source = ROOT / asset["source_path"]
            assert packaged.is_file()
            assert packaged.read_bytes() == source.read_bytes()
            assert hashlib.sha256(packaged.read_bytes()).hexdigest() == asset["sha256"]
            assert asset["packaged_path"] == f"references/{asset['source_path']}"
            assert "references/shared/shared/" not in asset["packaged_path"]

    selector_manifest = json.loads(
        (first / "model-selector/asset-manifest.json").read_text(encoding="utf-8")
    )
    packaged_cards = {
        item["source_path"]
        for item in selector_manifest["assets"]
        if item["source_path"].startswith("shared/knowledge/model-cards/")
    }
    source_cards = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "shared/knowledge/model-cards").rglob("*.md")
    }
    assert packaged_cards == source_cards


def test_check_cli_succeeds_without_persistent_output() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/package_codex_skills.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"skills": 12, "status": "ok"}


def test_check_detects_drift_in_an_existing_package(tmp_path: Path) -> None:
    output = tmp_path / "skills"
    package_skills(ROOT, output)
    verify_packaged_output(ROOT, output)

    skill_file = output / "solver" / "SKILL.md"
    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
    with pytest.raises(ValueError, match="package drift"):
        verify_packaged_output(ROOT, output)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/package_codex_skills.py",
            "--check",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "failed"


@pytest.mark.parametrize(
    ("skill", "modules"),
    [
        ("submission-auditor", ["cumcm_toolkit.review.engine", "cumcm_toolkit.review.inputs", "cumcm_toolkit.latex.citation_check", "cumcm_toolkit.pdf.inspect"]),
        ("repro-reviewer", ["cumcm_toolkit.review.engine", "cumcm_toolkit.review.inputs"]),
        ("model-reviewer", ["cumcm_toolkit.review.engine", "cumcm_toolkit.review.inputs"]),
        ("paper-reviewer", ["cumcm_toolkit.review.engine", "cumcm_toolkit.review.inputs", "cumcm_toolkit.evidence.linker", "cumcm_toolkit.latex.citation_check"]),
        ("red-team-reviewer", ["cumcm_toolkit.review.engine", "cumcm_toolkit.review.inputs", "cumcm_toolkit.evidence.citation_linker", "cumcm_toolkit.latex.citation_check"]),
    ],
)
def test_packaged_reviewers_have_importable_transitive_runtime_closure(
    tmp_path: Path, skill: str, modules: list[str]
) -> None:
    output = tmp_path / "skills"
    package_skills(ROOT, output)
    references = output / skill / "references"
    code = (
        "import importlib,sys;"
        f"sys.path[:0]=[{str(references)!r},{str(references / 'toolkit/src')!r}];"
        f"[importlib.import_module(name) for name in {modules!r}]"
    )
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
