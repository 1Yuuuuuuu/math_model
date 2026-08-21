import json
import socket
import subprocess
import sys

from scripts.validate_contracts import make_validator, validate_catalog


def test_validator_uses_an_explicit_offline_registry(project_root, tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "contract-workbench"
    import shutil

    shutil.copytree(project_root / "shared", sandbox / "shared")
    schema_path = sandbox / "shared/contracts/error.schema.json"
    schema_path.write_text(json.dumps({"$ref": "https://example.invalid/never-fetch"}), encoding="utf-8")
    network_calls: list[tuple[object, object]] = []

    def reject_network(address, *args, **kwargs):
        network_calls.append((address, args))
        raise AssertionError("validator attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)

    errors, contract_count = validate_catalog(sandbox)

    assert contract_count == 9
    assert errors and errors[0].startswith("error:")
    assert network_calls == []
    assert make_validator({"type": "object"}).format_checker is not None


def test_cli_returns_stable_failure_json_for_an_unresolved_remote_ref(project_root, tmp_path) -> None:
    sandbox = tmp_path / "contract-workbench"
    import shutil

    shutil.copytree(project_root / "shared", sandbox / "shared")
    shutil.copytree(project_root / "scripts", sandbox / "scripts")
    (sandbox / "shared/contracts/error.schema.json").write_text(
        json.dumps({"$ref": "https://example.invalid/never-fetch"}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/validate_contracts.py"],
        cwd=sandbox,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["contracts"] == 9
    assert payload["errors"] and payload["errors"][0].startswith("error:")
    assert "Traceback" not in result.stderr
