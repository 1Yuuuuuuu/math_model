from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from adapters.codex.routing import solver_execution_mode
from cumcm_toolkit.models import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


ROOT = Path(__file__).resolve().parents[3]

NEW_MODELS = {
    "topsis",
    "entropy-weight",
    "ahp",
    "grey-relational-analysis",
    "linear-programming",
    "integer-programming",
    "nonlinear-programming",
    "grey-prediction-gm11",
    "arima",
    "exponential-smoothing",
    "nonlinear-regression",
    "normalization",
    "interpolation",
    "anomaly-detection",
    "pca",
    "correlation-analysis",
    "confidence-interval",
    "parametric-test",
    "nonparametric-test",
    "anova",
    "logistic-regression",
    "dbscan",
    "hierarchical-clustering",
}
EXISTING_MODELS = {"linear-regression", "decision-tree", "kmeans"}

_MINIMAL_PAYLOADS: dict[str, dict[str, object]] = {
    "topsis": {"matrix": [[4, 1], [1, 4]], "criteria": ["benefit", "cost"]},
    "entropy-weight": {
        "matrix": [[1, 8], [2, 4], [4, 1]],
        "criteria": ["benefit", "cost"],
    },
    "ahp": {"pairwise_matrix": [[1, 2], [0.5, 1]]},
    "grey-relational-analysis": {
        "reference": [1, 2, 3],
        "comparatives": [[1, 2, 3], [3, 2, 1]],
    },
    "linear-programming": {"objective": [1], "sense": "minimize", "bounds": [[0, 1]]},
    "integer-programming": {
        "objective": [1],
        "sense": "maximize",
        "bounds": [[0, 2]],
        "integrality": [1],
    },
    "nonlinear-programming": {
        "objective": {
            "op": "power",
            "args": [
                {
                    "op": "subtract",
                    "args": [
                        {"op": "variable", "index": 0},
                        {"op": "constant", "value": 3},
                    ],
                },
                {"op": "constant", "value": 2},
            ],
        },
        "initial": [0],
        "bounds": [[-10, 10]],
        "sense": "minimize",
        "constraints": [],
    },
    "grey-prediction-gm11": {
        "series": [2.874, 3.278, 3.795, 4.435, 5.199],
        "forecast_steps": 1,
    },
    "arima": {
        "series": [
            10.0,
            10.66829419696158,
            11.181859485365136,
            11.528224001611973,
            11.848639500938415,
            12.308215145067372,
            12.944116900360214,
            13.631397319743758,
            14.197871649324677,
            14.582423697048,
        ],
        "order": [1, 1, 0],
        "forecast_steps": 1,
    },
    "exponential-smoothing": {
        "series": [10.0, 10.3, 10.6, 10.9, 11.2, 11.5, 11.8, 12.1],
        "forecast_steps": 1,
        "trend": "add",
        "seasonal": None,
        "damped_trend": False,
    },
    "nonlinear-regression": {
        "family": "polynomial",
        "x": [-2.0, -1.0, 0.0, 1.0, 2.0],
        "y": [9.0, 2.0, 1.0, 6.0, 17.0],
        "degree": 2,
        "predict_x": [3.0],
    },
    "normalization": {"matrix": [[1, 2], [3, 4]], "method": "minmax"},
    "interpolation": {"x": [0, 1], "y": [0, 2], "new_x": [0.5]},
    "anomaly-detection": {"matrix": [[1], [1], [1], [10]], "method": "iqr"},
    "pca": {
        "matrix": [[1, 2], [2, 3], [3, 4]],
        "components": 1,
        "standardize": False,
    },
    "correlation-analysis": {
        "x": [1, 2, 3],
        "y": [2, 4, 6],
        "method": "pearson",
    },
    "confidence-interval": {
        "method": "mean-t",
        "sample": [2, 3, 5, 8],
        "confidence": 0.95,
    },
    "parametric-test": {
        "test": "one-sample-t",
        "sample": [2, 3, 5, 8],
        "population_mean": 1,
    },
    "nonparametric-test": {
        "test": "mann-whitney-u",
        "sample_a": [1, 2, 3],
        "sample_b": [4, 6, 8],
    },
    "anova": {"groups": [[1, 2, 3], [4, 5, 6]]},
    "linear-regression": {
        "X": [[1.0], [2.0], [3.0]],
        "y": [3.0, 5.0, 7.0],
        "predict_X": [[4.0]],
    },
    "decision-tree": {
        "X": [[0.0], [1.0], [2.0], [3.0]],
        "y": ["low", "low", "high", "high"],
        "params": {"max_depth": 1},
        "seed": 7,
    },
    "logistic-regression": {
        "X": [[-2.0], [-1.0], [1.0], [2.0]],
        "y": ["negative", "negative", "positive", "positive"],
        "params": {"C": 1000.0, "max_iter": 1000, "solver": "liblinear"},
        "seed": 7,
    },
    "kmeans": {
        "X": [[0.0, 0.0], [0.0, 2.0], [10.0, 10.0], [10.0, 12.0]],
        "params": {"n_clusters": 2, "n_init": 10},
        "seed": 7,
    },
    "dbscan": {
        "X": [[0.0], [0.1], [5.0], [5.1]],
        "params": {"eps": 0.25, "min_samples": 2},
    },
    "hierarchical-clustering": {
        "X": [[0.0], [0.2], [5.0], [5.2]],
        "params": {"n_clusters": 2, "linkage": "complete", "metric": "euclidean"},
    },
}


def test_exact_new_inventory_and_minimum_total() -> None:
    ids = {item["model_id"] for item in list_capabilities()}

    assert NEW_MODELS == {
        "topsis", "entropy-weight", "ahp", "grey-relational-analysis",
        "linear-programming", "integer-programming", "nonlinear-programming",
        "grey-prediction-gm11", "arima", "exponential-smoothing", "nonlinear-regression",
        "normalization", "interpolation", "anomaly-detection", "pca",
        "correlation-analysis", "confidence-interval", "parametric-test",
        "nonparametric-test", "anova", "logistic-regression", "dbscan",
        "hierarchical-clustering",
    }
    assert NEW_MODELS <= ids
    assert EXISTING_MODELS <= ids
    assert len(ids) >= 26
    assert set(_MINIMAL_PAYLOADS) == ids


@pytest.mark.parametrize("capability", list_capabilities(), ids=lambda item: item["model_id"])
def test_every_registered_capability_executes_through_public_entrypoint(
    capability: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    model_id = capability["model_id"]
    assert isinstance(model_id, str)

    monkeypatch.setenv("LOKY_MAX_CPU_COUNT", "1")
    result = execute(model_id, _MINIMAL_PAYLOADS[model_id])

    assert result["status"] == "succeeded"
    assert result["model_id"] == model_id
    assert result["executor"] == capability["executor"]


@pytest.mark.parametrize("model_id", sorted(NEW_MODELS | EXISTING_MODELS))
def test_every_real_capability_routes_to_execute(model_id: str) -> None:
    assert solver_execution_mode(model_id) == "execute"


@pytest.mark.parametrize("model_id", ["heuristic", "dynamic-programming", "unknown-model"])
def test_unregistered_and_knowledge_card_only_capabilities_are_plan_only(model_id: str) -> None:
    if model_id != "unknown-model":
        assert (ROOT / "shared" / "knowledge" / "model-cards" / "optimization" / f"{model_id}.md").is_file()
    assert solver_execution_mode(model_id) == "plan-only"


@pytest.mark.parametrize("model_id", [None, 0, [], {}, "", " \t\n"])
def test_solver_execution_mode_rejects_invalid_model_ids_exactly(model_id: object) -> None:
    with pytest.raises(ValueError) as raised:
        solver_execution_mode(model_id)  # type: ignore[arg-type]
    assert str(raised.value) == "model_id must be a non-empty string"


def test_builtin_registration_is_lazy_in_a_fresh_process() -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "toolkit" / "src")}
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "from cumcm_toolkit.models import specifications; "
            "assert not any(name.startswith('cumcm_toolkit.models.executors.') "
            "for name in sys.modules); "
            "inventory = specifications.list_capabilities(); "
            "assert len(inventory) >= 26; "
            "assert any(name.startswith('cumcm_toolkit.models.executors.') "
            "for name in sys.modules)",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


def test_builtin_collision_failure_leaves_the_global_registry_usable() -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "toolkit" / "src")}
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cumcm_toolkit.models.specifications import ("
            "ModelSpec, get_spec, list_capabilities, register_spec); "
            "collision = ModelSpec("
            "'topsis', 'evaluation', "
            "'shared/knowledge/model-cards/evaluation/topsis.md', "
            "True, False, ('matrix', 'criteria'), lambda payload: {})\n"
            "try:\n"
            "    register_spec(collision)\n"
            "except ValueError as error:\n"
            "    assert str(error) == 'duplicate model_id: topsis'\n"
            "else:\n"
            "    raise AssertionError('built-in collision was accepted')\n"
            "first = list_capabilities(); "
            "assert len(first) == 26; "
            "assert get_spec('topsis').model_id == 'topsis'; "
            "assert list_capabilities() == first",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


def test_registry_builtins_are_deterministic_and_do_not_depend_on_adapters() -> None:
    first = list_capabilities()
    assert first == list_capabilities()
    for capability in first:
        assert get_spec(capability["model_id"]).model_id == capability["model_id"]
    assert first == list_capabilities()

    environment = {**os.environ, "PYTHONPATH": str(ROOT / "toolkit" / "src")}
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['adapters'] = None; "
            "from cumcm_toolkit.models.specifications import get_spec, list_capabilities; "
            "assert get_spec('topsis').model_id == 'topsis'; "
            "assert len(list_capabilities()) >= 26",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
