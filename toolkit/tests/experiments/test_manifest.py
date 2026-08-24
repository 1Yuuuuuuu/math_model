import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.experiments.manifest import (
    create_experiment_record,
    derive_experiment_id,
)
from scripts.validate_contracts import load_json, make_validator


def test_experiment_id_is_deterministic_across_parameter_order() -> None:
    first = derive_experiment_id(["art_raw_data"], "art_solve_code", {"a": 1, "b": 2}, 7)
    second = derive_experiment_id(["art_raw_data"], "art_solve_code", {"b": 2, "a": 1}, 7)
    assert first == second
    assert first.startswith("exp_")
    assert len(first) == 4 + 24


def test_experiment_id_changes_with_seed_or_input() -> None:
    base = derive_experiment_id(["art_raw_data"], "art_solve_code", {}, 7)
    assert base != derive_experiment_id(["art_raw_data"], "art_solve_code", {}, 8)
    assert base != derive_experiment_id(["art_other"], "art_solve_code", {}, 7)


def test_experiment_record_validates_against_phase0_schema(project_root: Path, tmp_path: Path) -> None:
    lock = project_root / "uv.lock"
    if not lock.is_file():
        pytest.skip("uv.lock not present")
    record = create_experiment_record(
        input_artifact_ids=["art_raw_data"],
        code_artifact_id="art_solve_code",
        parameters={"max_iterations": 1000},
        random_seed=7,
        status="succeeded",
        output_artifact_ids=["art_result_table"],
        metrics={"rmse": 0.125},
        project_root=project_root,
    )
    schema = load_json(project_root / "shared/contracts/experiment.schema.json")
    validator = make_validator(schema)
    assert list(validator.iter_errors(record)) == []
    assert record["environment"]["python_version"] == "3.11"
    assert record["environment"]["lock_sha256"] == lock_sha256_expected(lock)


def lock_sha256_expected(lock: Path) -> str:
    import hashlib

    return hashlib.sha256(lock.read_bytes()).hexdigest()


def test_experiment_record_rejects_invalid_status(project_root: Path) -> None:
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters={},
            random_seed=None,
            status="exploded",
            output_artifact_ids=[],
            metrics={},
            project_root=project_root,
        )


def test_experiment_id_recomputable_from_saved_record(project_root: Path) -> None:
    parameters = {"nested": {"layers": 3, "dropout": 0.1}, "optimizer": "adam"}
    record = create_experiment_record(
        input_artifact_ids=["art_raw_data"],
        code_artifact_id="art_solve_code",
        parameters=parameters,
        random_seed=7,
        status="succeeded",
        output_artifact_ids=["art_result_table"],
        metrics={"rmse": 0.125},
        project_root=project_root,
    )
    recomputed = derive_experiment_id(
        record["input_artifact_ids"],
        record["code_artifact_id"],
        record["parameters"],
        record["random_seed"],
    )
    assert recomputed == record["experiment_id"]


def test_create_experiment_record_rejects_non_dict_parameters(project_root: Path) -> None:
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters=[["a", 1]],
            random_seed=None,
            status="succeeded",
            output_artifact_ids=[],
            metrics={},
            project_root=project_root,
        )
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters={},
            random_seed=None,
            status="succeeded",
            output_artifact_ids=[],
            metrics=[["loss", 1.0]],
            project_root=project_root,
        )


def test_create_experiment_record_rejects_non_finite_numbers(project_root: Path) -> None:
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters={"loss": float("nan")},
            random_seed=None,
            status="succeeded",
            output_artifact_ids=[],
            metrics={},
            project_root=project_root,
        )
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters={},
            random_seed=None,
            status="succeeded",
            output_artifact_ids=[],
            metrics={"loss": float("inf")},
            project_root=project_root,
        )


def _run_manifest_cli(project_root: Path, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.experiments.manifest",
         "--input-artifacts", "art_raw_data",
         "--code-artifact", "art_solve_code",
         "--status", "succeeded",
         *extra_args],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": str(project_root / "toolkit" / "src") + os.pathsep + str(project_root)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_manifest_cli_rejects_array_parameters(project_root: Path) -> None:
    result = _run_manifest_cli(project_root, ["--parameters", '[["a",1]]'])
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert "parameters must be a JSON object" in payload["error"]


def test_manifest_cli_rejects_nonfinite_metrics(project_root: Path) -> None:
    result = _run_manifest_cli(project_root, ["--metrics", '{"loss":NaN}'])
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert "non-standard JSON constant" in payload["error"]
