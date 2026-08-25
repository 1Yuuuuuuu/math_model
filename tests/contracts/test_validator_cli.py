import json
from pathlib import Path
import shutil
import subprocess
import sys


def test_validator_cli_reports_success(project_root) -> None:
    result = run_validator(project_root)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"status": "ok", "contracts": 15, "errors": []}


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
    assert payload["contracts"] == 15
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
    assert payload["contracts"] == 16
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


def test_validator_rejects_nonstandard_json_constants_in_catalog_schema_and_fixture(
    project_root, tmp_path
) -> None:
    cases = (
        ("shared/contracts/catalog.json", '"catalog_version": "1.0"', '"catalog_version": NaN', 0),
        ("shared/contracts/error.schema.json", '"title": "Tool error envelope"', '"title": Infinity', 15),
        (
            "shared/fixtures/contracts/valid/error.json",
            '"recoverable":true',
            '"recoverable":-Infinity',
            15,
        ),
    )
    for index, (relative_path, old, new, expected_count) in enumerate(cases):
        sandbox = make_sandbox(project_root, tmp_path / str(index))
        path = sandbox / relative_path
        source = path.read_text(encoding="utf-8")
        assert old in source
        path.write_text(source.replace(old, new, 1), encoding="utf-8")

        result = run_validator(sandbox)

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "failed"
        assert payload["contracts"] == expected_count
        assert len(payload["errors"]) == 1


def test_validator_requires_supported_catalog_version(project_root, tmp_path) -> None:
    for index, version in enumerate((None, "2.0", 1.0)):
        sandbox = make_sandbox(project_root, tmp_path / str(index))
        catalog_path = sandbox / "shared/contracts/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        if version is None:
            del catalog["catalog_version"]
        else:
            catalog["catalog_version"] = version
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        result = run_validator(sandbox)

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert json.loads(result.stdout) == {
            "status": "failed",
            "contracts": 0,
            "errors": ["catalog: catalog_version must be the string 1.0"],
        }


def test_importing_validator_as_a_library_does_not_change_bytecode_policy(project_root) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.dont_write_bytecode = False; "
                "import scripts.validate_contracts; "
                "print(sys.dont_write_bytecode)"
            ),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


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
    assert payload["contracts"] == 15
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
    assert payload["contracts"] == 15
    assert payload["errors"] == [
        f"error: catalog path must be workspace-relative: {catalog['contracts'][0]['schema']}"
    ]


def test_validator_rejects_superscript_windows_device_catalog_paths(
    project_root, tmp_path
) -> None:
    for index, invalid_path in enumerate(
        ("folder/COM¹", "COM².txt", "COM³.tar.gz", "LPT¹", "LPT².log", "LPT³.tar.gz")
    ):
        sandbox = make_sandbox(project_root, tmp_path / str(index))
        catalog_path = sandbox / "shared/contracts/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["contracts"][0]["schema"] = invalid_path
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

        result = run_validator(sandbox)

        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        payload = json.loads(result.stdout)
        assert payload == {
            "status": "failed",
            "contracts": 15,
            "errors": [f"error: catalog path must be portable: {invalid_path}"],
        }


def test_validator_rejects_missing_or_empty_contract_catalogs(project_root, tmp_path) -> None:
    for contracts in (None, []):
        sandbox = make_sandbox(project_root, tmp_path / str(contracts))
        catalog_path = sandbox / "shared/contracts/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        if contracts is None:
            del catalog["contracts"]
        else:
            catalog["contracts"] = contracts
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        result = run_validator(sandbox)

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "failed"
        assert payload["contracts"] == 0
        assert len(payload["errors"]) == 1
        assert "Traceback" not in result.stderr


def test_validator_rejects_non_list_contracts(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"] = {"id": "error"}
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["contracts"] == 0
    assert payload["errors"] == ["catalog: contracts must be a non-empty list"]
    assert "Traceback" not in result.stderr


def test_validator_rejects_non_object_contract_entries(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"][0] = []
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["contracts"] == 15
    assert payload["errors"] == ["catalog: contract entry at index 0 must be an object"]
    assert "Traceback" not in result.stderr


def test_validator_rejects_missing_contract_entry_fields(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    catalog_path = sandbox / "shared/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["contracts"][0] = {"id": "error"}
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["errors"] == [
        "error: missing required catalog fields: schema, valid_examples, invalid_examples"
    ]
    assert "Traceback" not in result.stderr


def test_validator_rejects_invalid_entry_field_shapes(project_root, tmp_path) -> None:
    cases = [
        ("id", 1),
        ("id", ""),
        ("id", "Error"),
        ("id", []),
        ("schema", 1),
        ("schema", ""),
        ("valid_examples", "fixture.json"),
        ("valid_examples", []),
        ("valid_examples", [1]),
        ("invalid_examples", "fixture.json"),
        ("invalid_examples", []),
        ("invalid_examples", [1]),
    ]
    for index, (field, value) in enumerate(cases):
        sandbox = make_sandbox(project_root, tmp_path / str(index))
        catalog_path = sandbox / "shared/contracts/catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["contracts"][0][field] = value
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        result = run_validator(sandbox)

        assert result.returncode == 1, (field, value, result.stderr)
        payload = json.loads(result.stdout)
        assert payload["status"] == "failed"
        assert len(payload["errors"]) == 1
        assert "Traceback" not in result.stderr


def test_validator_reports_invalid_utf8_catalog_without_traceback(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    (sandbox / "shared/contracts/catalog.json").write_bytes(b"\xff")

    result = run_validator(sandbox)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["contracts"] == 0
    assert payload["status"] == "failed"
    assert payload["errors"][0].startswith("catalog:")
    assert "Traceback" not in result.stderr


def test_validator_reports_invalid_utf8_schema_and_fixture_without_traceback(project_root, tmp_path) -> None:
    for index, relative_path in enumerate(
        [
            "shared/contracts/error.schema.json",
            "shared/fixtures/contracts/valid/error.json",
        ]
    ):
        sandbox = make_sandbox(project_root, tmp_path / str(index))
        (sandbox / relative_path).write_bytes(b"\xff")

        result = run_validator(sandbox)

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["contracts"] == 15
        assert payload["status"] == "failed"
        assert len(payload["errors"]) == 1
        assert payload["errors"][0].startswith("error:")
        assert "Traceback" not in result.stderr


def test_validator_writes_no_bytecode_or_other_files(project_root, tmp_path) -> None:
    sandbox = make_sandbox(project_root, tmp_path)
    remove_bytecode_directories(sandbox)
    before = filesystem_listing(sandbox)

    result = run_validator(sandbox)

    assert result.returncode == 0, result.stderr
    assert filesystem_listing(sandbox) == before


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


def remove_bytecode_directories(root: Path) -> None:
    for directory in root.rglob("__pycache__"):
        shutil.rmtree(directory)


def filesystem_listing(root: Path) -> list[str]:
    return sorted(
        f"{path.relative_to(root).as_posix()}{'/' if path.is_dir() else ''}"
        for path in root.rglob("*")
    )
