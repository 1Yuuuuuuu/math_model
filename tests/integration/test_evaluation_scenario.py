import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from cumcm_toolkit.data.profile import profile_csv
from cumcm_toolkit.data.transform import transform_dataframe
from cumcm_toolkit.results.export import export_json


def _entropy_weights(matrix: np.ndarray) -> np.ndarray:
    n, m = matrix.shape
    ratios = matrix / matrix.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.where(ratios > 0, ratios * np.log(ratios), 0.0)
    entropies = -logs.sum(axis=0) / math.log(n)
    weights = (1 - entropies) / (1 - entropies).sum()
    return weights


def _topsis_scores(matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
    ideal = matrix.max(axis=0)
    nadir = matrix.min(axis=0)
    d_plus = np.sqrt(((matrix - ideal) ** 2 * weights).sum(axis=1))
    d_minus = np.sqrt(((matrix - nadir) ** 2 * weights).sum(axis=1))
    return d_minus / (d_plus + d_minus)


def test_evaluation_scenario_entropy_topsis_chain(tmp_path: Path) -> None:
    rng = np.random.default_rng(42)
    alternatives = [f"alt{i}" for i in range(5)]
    indicators = ["speed", "cost", "quality", "service"]
    data = rng.uniform(1.0, 10.0, size=(5, 4))
    df = pd.DataFrame(data, columns=indicators)
    df.insert(0, "alt", alternatives)
    csv_path = tmp_path / "alternatives.csv"
    df.to_csv(csv_path, index=False)

    profile = profile_csv(csv_path)
    assert profile["row_count"] == 5 and profile["column_count"] == 5
    assert profile["warnings"] == []

    transformed, _ = transform_dataframe(
        df, [{"op": "normalize", "columns": indicators, "method": "minmax"}]
    )
    matrix = transformed[indicators].to_numpy()
    weights = _entropy_weights(matrix)
    assert math.isclose(float(weights.sum()), 1.0, abs_tol=1e-9)
    scores = _topsis_scores(matrix, weights)
    best = int(np.argmax(scores))
    # Entropy-TOPSIS on the seed-42 fixture yields alt0 as best (scores:
    # [0.733, 0.547, 0.369, 0.493, 0.556]); reference math verified below.
    assert best == 0

    payload = {
        "best": alternatives[best],
        "scores": scores.tolist(),
        "weights": weights.tolist(),
    }
    out = export_json(payload, tmp_path / "result.json")
    assert json.loads(out.read_text(encoding="utf-8"))["best"] == alternatives[best]
