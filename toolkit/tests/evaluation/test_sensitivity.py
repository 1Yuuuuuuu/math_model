import pytest

from cumcm_toolkit.evaluation.sensitivity import sensitivity_report


def test_sensitivity_range_and_conclusion() -> None:
    def evaluate(params: dict[str, float]) -> float:
        return params["a"] * 10 + params["b"]

    report = sensitivity_report(
        base_params={"a": 1.0, "b": 1.0},
        perturb={"a": [0.9, 1.0, 1.1], "b": [0.5, 1.0, 1.5]},
        evaluate=evaluate,
    )
    a = report["parameters"]["a"]
    b = report["parameters"]["b"]
    assert a["range"] == pytest.approx(2.0)
    assert b["range"] == pytest.approx(1.0)
    assert "a" in report["conclusion"]


def test_sensitivity_skips_unknown_param_with_warning() -> None:
    report = sensitivity_report(
        base_params={"a": 1.0},
        perturb={"a": [0.9, 1.0, 1.1], "zz": [0.0, 1.0]},
        evaluate=lambda p: p["a"] * 10,
    )
    assert "zz" not in report["parameters"]
    assert "a" in report["parameters"]
    assert any("zz" in w for w in report["warnings"])


def test_sensitivity_fails_when_all_params_unknown() -> None:
    with pytest.raises(ValueError):
        sensitivity_report(
            base_params={"a": 1.0},
            perturb={"zz": [0.0, 1.0]},
            evaluate=lambda p: p["a"],
        )


def test_sensitivity_fails_when_perturb_empty() -> None:
    with pytest.raises(ValueError):
        sensitivity_report(base_params={"a": 1.0}, perturb={}, evaluate=lambda p: p["a"])


def test_sensitivity_fails_when_no_point_succeeds() -> None:
    def evaluate(params: dict[str, float]) -> float:
        raise RuntimeError("boom")

    with pytest.raises(ValueError):
        sensitivity_report(base_params={"a": 1.0}, perturb={"a": [1.0]}, evaluate=evaluate)


def test_sensitivity_non_finite_point_becomes_none_with_warning() -> None:
    def evaluate(params: dict[str, float]) -> float:
        return float("inf") if params["a"] > 1.0 else params["a"]

    report = sensitivity_report(
        base_params={"a": 1.0}, perturb={"a": [0.5, 1.5, 2.5]}, evaluate=evaluate
    )
    assert report["parameters"]["a"]["results"] == [0.5, None, None]
    assert any("non-finite" in w for w in report["warnings"])


def test_sensitivity_all_non_finite_points_fail() -> None:
    def evaluate(params: dict[str, float]) -> float:
        return float("inf")

    with pytest.raises(ValueError):
        sensitivity_report(base_params={"a": 1.0}, perturb={"a": [1.0, 2.0]}, evaluate=evaluate)
