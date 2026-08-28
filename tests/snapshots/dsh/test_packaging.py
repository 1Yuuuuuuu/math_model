from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import scripts.package_dsh_assets as pkg
from scripts.package_dsh_assets import (
    build_manifest,
    package_assets,
    validate_resource_path,
    verify_manifest,
)

ROOT = Path(__file__).resolve().parents[3]

RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

FROZEN = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _make_fake_repo(tmp_path: Path) -> Path:
    """Minimal replica of the shared/ tree for drift tampering (never touches the real repo)."""
    repo = tmp_path / "repo"
    (repo / "shared/contracts").mkdir(parents=True)
    (repo / "shared/templates").mkdir(parents=True)
    (repo / "shared/knowledge/model-cards/classification").mkdir(parents=True)
    (repo / "shared/knowledge/foundations").mkdir(parents=True)
    (repo / "shared/workflows").mkdir(parents=True)
    (repo / "shared/rubrics").mkdir(parents=True)
    (repo / "adapters/codex/skills/fake-agent/agents").mkdir(parents=True)
    (repo / "adapters/dsh/presets/cumcm-agent").mkdir(parents=True)
    shutil.copy2(
        ROOT / "shared/contracts/error.schema.json",
        repo / "shared/contracts/error.schema.json",
    )
    shutil.copy2(
        ROOT / "shared/knowledge/model-cards/classification/kmeans.md",
        repo / "shared/knowledge/model-cards/classification/kmeans.md",
    )
    shutil.copy2(
        ROOT / "shared/knowledge/foundations/cross-validation.md",
        repo / "shared/knowledge/foundations/cross-validation.md",
    )
    shutil.copy2(
        ROOT / "shared/knowledge/model-catalog.yaml",
        repo / "shared/knowledge/model-catalog.yaml",
    )
    shutil.copy2(
        ROOT / "shared/workflows/cumcm-72h.yaml",
        repo / "shared/workflows/cumcm-72h.yaml",
    )
    shutil.copy2(
        ROOT / "shared/rubrics/submission.yaml",
        repo / "shared/rubrics/submission.yaml",
    )
    shutil.copy2(
        ROOT / "adapters/codex/skills/solver/agents/openai.yaml",
        repo / "adapters/codex/skills/fake-agent/agents/openai.yaml",
    )
    shutil.copy2(
        ROOT / "adapters/dsh/presets/cumcm-agent/cordis.yml",
        repo / "adapters/dsh/presets/cumcm-agent/cordis.yml",
    )
    return repo


@pytest.mark.parametrize(
    "unsafe",
    [
        "",
        "../secret.txt",
        "/absolute/file",
        "C:/secret.txt",
        "shared/../etc/passwd",
        "shared/contracts/../../escape",
        r"shared\contracts\error.schema.json",
    ],
)
def test_resource_paths_cannot_escape_repository(unsafe: str) -> None:
    with pytest.raises(ValueError, match="unsafe resource path"):
        validate_resource_path(unsafe)


def test_resource_path_may_hash_reference_codex_agents() -> None:
    path = validate_resource_path("adapters/codex/skills/solver/agents/openai.yaml")
    assert path.as_posix() == "adapters/codex/skills/solver/agents/openai.yaml"


def test_manifest_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pkg, "_utc_now", lambda: FROZEN)
    first = tmp_path / "first"
    second = tmp_path / "second"
    package_assets(ROOT, first)
    package_assets(ROOT, second)
    assert _tree_hash(first) == _tree_hash(second)


def test_manifest_shape_and_generated_at(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "1.0"
    assert RFC3339.match(manifest["generated_at"])
    assert set(manifest["asset_categories"]) == {
        "contracts",
        "templates",
        "knowledge",
        "model-cards",
        "workflow",
        "presets",
    }
    assert isinstance(manifest["assets"], dict)
    assert manifest["assets"]


def test_manifest_assets_exist_hashes_correct_and_paths_safe(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    resolved_root = ROOT.resolve()
    for relative, digest in manifest["assets"].items():
        source = ROOT / relative
        assert source.is_file(), relative
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        assert not relative.startswith(("/", "\\"))
        assert "\\" not in relative
        assert ".." not in relative.split("/")
        try:
            source.resolve().relative_to(resolved_root)
        except ValueError:
            pytest.fail(f"asset escapes repository: {relative}")
    for category, paths in manifest["asset_categories"].items():
        assert sorted(paths) == paths, category
        assert set(paths) <= set(manifest["assets"]), category


def test_categories_match_repository_trees(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    categories = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )["asset_categories"]

    def tree(relative: str) -> list[str]:
        return sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / relative).rglob("*")
            if path.is_file()
        )

    assert categories["contracts"] == sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "shared/contracts").glob("*.json")
    )
    assert categories["templates"] == tree("shared/templates")
    assert categories["knowledge"] == tree("shared/knowledge")
    assert categories["model-cards"] == tree("shared/knowledge/model-cards")
    codex_agents = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "adapters/codex/skills").glob("*/agents/openai.yaml")
    )
    assert categories["workflow"] == sorted(
        tree("shared/workflows")
        + tree("shared/rubrics")
        + ["shared/knowledge/model-catalog.yaml"]
        + codex_agents
    )
    assert categories["presets"] == tree("adapters/dsh/presets")


def test_contracts_category_covers_schemas_and_catalog(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    contracts = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )["asset_categories"]["contracts"]
    schemas = [path for path in contracts if path.endswith(".schema.json")]
    assert len(contracts) == 17
    assert len(schemas) == 16
    assert "shared/contracts/catalog.json" in contracts
    assert all(path.startswith("shared/contracts/") for path in contracts)


def test_model_cards_category_matches_codex_packager_coverage(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    cards = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )["asset_categories"]["model-cards"]
    source_cards = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "shared/knowledge/model-cards").rglob("*.md")
    }
    assert set(cards) == source_cards
    assert len(cards) == 33


def test_output_contains_only_manifest(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    assert sorted(path.name for path in output.rglob("*")) == ["manifest.json"]


def test_verify_manifest_reports_drift_on_tampered_source(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    output = tmp_path / "out"
    package_assets(repo, output)
    assert verify_manifest(repo, output) == {"missing": [], "extra": [], "changed": []}

    card = repo / "shared/knowledge/model-cards/classification/kmeans.md"
    card.write_text(card.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
    report = verify_manifest(repo, output)
    assert report == {
        "missing": [],
        "extra": [],
        "changed": ["shared/knowledge/model-cards/classification/kmeans.md"],
    }

    card.unlink()
    report = verify_manifest(repo, output)
    assert report["missing"] == ["shared/knowledge/model-cards/classification/kmeans.md"]
    assert report["changed"] == []

    added = repo / "shared/knowledge/writing/extra.md"
    added.parent.mkdir(parents=True, exist_ok=True)
    added.write_text("new asset\n", encoding="utf-8")
    report = verify_manifest(repo, output)
    assert report["extra"] == ["shared/knowledge/writing/extra.md"]
    assert report["missing"] == ["shared/knowledge/model-cards/classification/kmeans.md"]


def test_check_cli_succeeds_without_drift(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    result = subprocess.run(
        [sys.executable, "scripts/package_dsh_assets.py", "--check", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["assets"] == len(build_manifest(ROOT)["assets"])


def test_check_cli_reports_drift_and_exits_one(tmp_path: Path) -> None:
    output = tmp_path / "out"
    package_assets(ROOT, output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = next(iter(manifest["assets"]))
    manifest["assets"][target] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/package_dsh_assets.py", "--check", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["changed"] == [target]


def test_check_cli_fails_when_manifest_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/package_dsh_assets.py",
            "--check",
            "--output",
            str(tmp_path / "nope"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "failed"
