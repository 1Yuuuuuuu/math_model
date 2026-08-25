import pytest

from cumcm_toolkit.evidence.linker import link_claim, link_claim_to_metrics, resolve_numeric_claims
from scripts.validate_contracts import load_json, make_validator


def _validator(project_root: pytest.FixtureRequest) -> object:
    schema = load_json(project_root / "shared/contracts/evidence-link.schema.json")
    return make_validator(schema)


def test_link_claim_validates_against_phase0_schema(project_root: pytest.FixtureRequest) -> None:
    record = link_claim(
        claim_id="clm_method_choice",
        claim_text="采用熵权法确定权重",
        artifact_id="art_result_table",
        experiment_id="exp_model_run",
        locator={"kind": "table", "value": "表1"},
        boundary="仅覆盖熵权法权重计算",
    )
    validator = _validator(project_root)
    assert list(validator.iter_errors(record)) == []


def test_link_claim_rejects_invalid_locator(project_root: pytest.FixtureRequest) -> None:
    with pytest.raises(ValueError):
        link_claim(
            claim_id="clm_bad", claim_text="x", artifact_id="art_x",
            experiment_id="exp_x", locator={"kind": "table"}, boundary="b",
        )


def test_link_claim_to_metrics_binds_number(tmp_path: pytest.FixtureRequest) -> None:
    experiment = {
        "schema_version": "1.0",
        "experiment_id": "exp_model_run",
        "input_artifact_ids": ["art_raw_data"],
        "code_artifact_id": "art_solve_code",
        "parameters": {},
        "random_seed": 7,
        "environment": {"python_version": "3.11", "lock_sha256": "a" * 64},
        "started_at": "2026-08-22T00:00:00+00:00",
        "finished_at": "2026-08-22T00:01:00+00:00",
        "status": "succeeded",
        "output_artifact_ids": ["art_result_table"],
        "metrics": {"rmse": 0.125},
    }
    record = link_claim_to_metrics(
        claim_id="clm_rmse", claim_text="RMSE 为 0.125",
        experiment_record=experiment, metric_keys=["rmse"], boundary="单次运行",
    )
    assert record["locator"] == {"kind": "metric", "value": "rmse"}
    assert record["artifact_id"] == "art_result_table"


def test_link_claim_to_metrics_missing_output_artifacts_fails() -> None:
    experiment = {"metrics": {"rmse": 0.125}, "experiment_id": "exp_model_run"}
    with pytest.raises(ValueError, match="no output artifact ids"):
        link_claim_to_metrics(
            claim_id="clm_x", claim_text="RMSE 为 0.125", experiment_record=experiment,
            metric_keys=["rmse"], boundary="b",
        )
    experiment["output_artifact_ids"] = []
    with pytest.raises(ValueError, match="no output artifact ids"):
        link_claim_to_metrics(
            claim_id="clm_x", claim_text="RMSE 为 0.125", experiment_record=experiment,
            metric_keys=["rmse"], boundary="b",
        )


def test_link_claim_to_metrics_rejects_missing_number() -> None:
    experiment = {"metrics": {"rmse": 0.125}, "output_artifact_ids": ["art_x"], "experiment_id": "exp_x"}
    with pytest.raises(ValueError):
        link_claim_to_metrics(
            claim_id="clm_x", claim_text="RMSE 为 0.9", experiment_record=experiment,
            metric_keys=["rmse"], boundary="b",
        )


def test_resolve_numeric_claims_all_resolved() -> None:
    # evidence-link records carry claim_text only (schema additionalProperties:false
    # forbids a metrics field), so matching is token-exact against claim_text.
    links = [
        {"claim_id": "clm_rmse", "claim_text": "RMSE 为 0.125"},
    ]
    result = resolve_numeric_claims("RMSE 为 0.125", links)
    assert result["status"] == "ok"
    assert result["unresolved"] == []
    assert [c["number"] for c in result["claims"]] == ["0.125"]


def test_resolve_numeric_claims_unresolved_fails() -> None:
    result = resolve_numeric_claims("精度 99.5%", [])
    assert result["status"] == "failed"
    assert any("99.5" in str(u) for u in result["unresolved"])


def test_resolve_numeric_claims_dedupes_numbers() -> None:
    links = [{"claim_id": "clm_x", "claim_text": "精度 99.5%"}]
    result = resolve_numeric_claims("精度 99.5% 与 99.5", links)
    assert result["status"] == "ok"
    assert len(result["claims"]) == 1, "duplicate numbers must collapse to one claim entry"


def test_resolve_numeric_claims_token_exact_matching() -> None:
    # "5" must NOT match the token "5.125" (substring matching would be a false positive).
    links = [{"claim_id": "clm_x", "claim_text": "值为 5.125"}]
    result = resolve_numeric_claims("值为 5", links)
    assert result["status"] == "failed"
    assert any(u["number"] == "5" for u in result["unresolved"])
    assert result["claims"] == []
    # and "0.125" must not match "5" or "5.125" substrings
    links = [{"claim_id": "clm_y", "claim_text": "值为 5"}]
    result = resolve_numeric_claims("RMSE 为 0.125", links)
    assert result["status"] == "failed"
    assert result["claims"] == []
