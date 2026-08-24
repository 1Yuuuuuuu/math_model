import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from cumcm_toolkit.data.profile import profile_csv
from cumcm_toolkit.results.export import export_json


def test_optimization_scenario_lp_to_export(tmp_path: Path) -> None:
    constraints = pd.DataFrame(
        {
            "constraint": ["c1", "c2"],
            "x0_coef": [1.0, 1.0],
            "x1_coef": [1.0, 0.0],
            "rhs": [10.0, 6.0],
        }
    )
    csv_path = tmp_path / "constraints.csv"
    constraints.to_csv(csv_path, index=False)
    profile = profile_csv(csv_path)
    assert profile["row_count"] == 2

    c = np.array([-1.0, -2.0])
    A_ub = np.array([[1.0, 1.0], [1.0, 0.0]])
    b_ub = np.array([10.0, 6.0])
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None), (0, None)], method="highs")
    assert result.success
    # True optimum of this LP: vertices are (0,0)->0, (6,0)->-6, (6,4)->-14,
    # (0,10)->-20, so the minimum is (0, 10) with fun -20 (the brief's claimed
    # (6,4)/-14 is feasible but NOT optimal).
    assert np.allclose(result.x, [0.0, 10.0], atol=1e-6)
    assert math.isclose(float(result.fun), -20.0, abs_tol=1e-6)

    out = export_json(
        {"x": result.x.tolist(), "objective": float(result.fun)},
        tmp_path / "opt.json",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["x"] == [0.0, 10.0]
