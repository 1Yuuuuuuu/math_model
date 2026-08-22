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
