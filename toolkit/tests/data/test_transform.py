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
