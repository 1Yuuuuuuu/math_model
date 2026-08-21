import json
from pathlib import Path
import shutil
import subprocess
import sys


def test_validator_cli_reports_success(project_root) -> None:
    result = run_validator(project_root)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"status": "ok", "contracts": 9, "errors": []}


def test_validator_reports_a_registered_invalid_fixture_that_becomes_valid(
    project_root, tmp_path
) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    invalid_fixture = sandbox / "shared/fixtures/contracts/invalid/error-missing-code.json"
    invalid_fixture.write_text(
        (sandbox / "shared/fixtures/contracts/valid/error.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 9
    assert payload["errors"] == [
        "error: invalid fixture passed: shared/fixtures/contracts/invalid/error-missing-code.json"
    ]


def test_validator_rejects_duplicate_catalog_ids(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"].append(catalog["contracts"][0])
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 10
    assert payload["errors"] == ["catalog: duplicate contract id"]


def test_validator_returns_stable_json_for_a_malformed_catalog(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    (sandbox / "shared/contracts/catalog.json").write_text("{", encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 0
    assert len(payload["errors"]) == 1
    assert payload["errors"][0].startswith("catalog:")


def test_validator_rejects_catalog_paths_that_escape_the_workspace(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"][0]["schema"] = "../outside.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 9
    assert payload["errors"] == ["error: catalog path escapes workspace: ../outside.json"]


def test_validator_rejects_absolute_catalog_paths(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"][0]["schema"] = str((sandbox / "shared/contracts/error.schema.json").resolve())
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 9
    assert payload["errors"] == [
        f"error: catalog path must be workspace-relative: {catalog['contracts'][0]['schema']}"
    ]


def make_sandbox(project_root: Path, tmp_path: Path) -> Path:
    sandbox = tmp_path / "contract-workbench"
    shutil.copytree(project_root / "shared", sandbox / "shared")
    shutil.copytree(project_root / "scripts", sandbox / "scripts")
    return sandbox


def run_validator(project_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/validate_contracts.py"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
