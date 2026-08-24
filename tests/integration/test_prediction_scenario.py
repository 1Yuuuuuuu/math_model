import json
import math
from pathlib import Path

import numpy as np

from cumcm_toolkit.evaluation.baselines import compare_to_baseline
from cumcm_toolkit.evaluation.metrics import regression_metrics
from cumcm_toolkit.evaluation.sensitivity import sensitivity_report
from cumcm_toolkit.models.runner import run_model
from cumcm_toolkit.results.export import export_json


def test_prediction_scenario_linear_recovery_to_export(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    n = 100
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    noise = rng.normal(scale=0.01, size=n)
    y = 2.0 * x1 - 1.0 * x2 + noise
    X = np.column_stack([x1, x2])

    result = run_model("linear-regression", X, y, seed=7)
    coef = result["fitted"].coef_
    assert np.allclose(coef, [2.0, -1.0], atol=0.05)

    y_pred = result["fitted"].predict(X)
    metrics = regression_metrics(y, y_pred)
    assert metrics["r2"] >= 0.99

    baseline = compare_to_baseline(y, y_pred, baseline_value=float(np.mean(y)))
    assert baseline["improvement"] is not None and baseline["improvement"] > 0.9

    def evaluate(params: dict[str, float]) -> float:
        predicted = params["c1"] * x1 + params["c2"] * x2
        return regression_metrics(y, predicted)["r2"]

    report = sensitivity_report(
        base_params={"c1": 2.0, "c2": -1.0},
        perturb={"c1": [1.5, 2.0, 2.5], "c2": [-0.5, -1.0, -1.5]},
        evaluate=evaluate,
    )
    assert report["conclusion"]
    assert set(report["parameters"]) == {"c1", "c2"}

    out = export_json({"r2": metrics["r2"], "conclusion": report["conclusion"]}, tmp_path / "pred.json")
    assert json.loads(out.read_text(encoding="utf-8"))["r2"] == metrics["r2"]
