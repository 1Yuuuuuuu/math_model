import pandas as pd
import pytest

from cumcm_toolkit.data.transform import transform_dataframe


def test_drop_and_fill_steps_apply_in_order() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [1, 2, 3], "c": [0, 0, 0]})
    out, record = transform_dataframe(
        df,
        [
            {"op": "fill_missing", "columns": ["a"], "value": 0.0},
            {"op": "drop_columns", "columns": ["c"]},
        ],
    )
    assert list(out.columns) == ["a", "b"]
    assert out["a"].isna().sum() == 0
    assert record["steps_applied"] == 2


def test_normalize_minmax() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    out, _ = transform_dataframe(df, [{"op": "normalize", "columns": ["x"], "method": "minmax"}])
    assert out["x"].tolist() == pytest.approx([0.0, 0.5, 1.0])


def test_unknown_op_fails_closed() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError):
        transform_dataframe(df, [{"op": "teleport", "columns": ["a"]}])


def test_missing_column_warns_but_continues() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    out, record = transform_dataframe(df, [{"op": "drop_columns", "columns": ["zz"]}])
    assert any("zz" in w for w in record["warnings"])


def test_drop_missing_with_missing_column_warns_and_continues() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0, None]})
    out, record = transform_dataframe(df, [{"op": "drop_missing", "subset": ["zz"]}])
    assert len(out) == 3
    assert any("zz" in w for w in record["warnings"])


def test_drop_missing_without_subset_drops_any_na() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [1, 2, 3]})
    out, _ = transform_dataframe(df, [{"op": "drop_missing"}])
    assert len(out) == 2
    assert out["a"].isna().sum() == 0


def test_non_dict_step_fails_closed() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError):
        transform_dataframe(df, [None])


def test_cast_invalid_dtype_fails_closed() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError):
        transform_dataframe(df, [{"op": "cast", "columns": ["a"], "dtype": "bogus"}])


def test_normalize_preserves_missing_mask() -> None:
    df = pd.DataFrame({"x": [5.0, 5.0, None]})
    out, record = transform_dataframe(df, [{"op": "normalize", "columns": ["x"], "method": "minmax"}])
    assert out["x"].iloc[0] == pytest.approx(0.0)
    assert out["x"].iloc[1] == pytest.approx(0.0)
    assert pd.isna(out["x"].iloc[2])
    assert any("constant" in w for w in record["warnings"])


def test_normalize_all_missing_stays_missing() -> None:
    df = pd.DataFrame({"x": [float("nan"), float("nan"), float("nan")]})
    out, record = transform_dataframe(df, [{"op": "normalize", "columns": ["x"], "method": "minmax"}])
    assert out["x"].isna().all()
    assert any("constant" in w for w in record["warnings"])


@pytest.mark.parametrize(
    "step",
    [
        {"op": "drop_columns", "columns": "ab"},
        {"op": "fill_missing", "columns": 1, "value": 0},
        {"op": "normalize", "columns": None, "method": "minmax"},
        {"op": "drop_missing", "subset": ["a", 1]},
        {"op": "to_datetime", "columns": "x"},
        {"op": "cast", "columns": "x", "dtype": "float64"},
    ],
)
def test_invalid_columns_rejected(step: dict[str, object]) -> None:
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4], "x": ["2024-01-01", "2024-01-02"]})
    with pytest.raises(ValueError):
        transform_dataframe(df, [step])


def test_invalid_step_leaves_input_untouched() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4]})
    original = df.copy()
    with pytest.raises(ValueError):
        transform_dataframe(df, [{"op": "drop_columns", "columns": "ab"}])
    assert df.equals(original)
