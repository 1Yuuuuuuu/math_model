import math
from pathlib import Path

import pandas as pd
import pytest

from cumcm_toolkit.data.profile import profile_csv, profile_dataframe


def test_profile_reports_shape_missing_and_warnings() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "score": [0.1, None, None, None],
            "group": ["a", "a", "b", "b"],
        }
    )
    result = profile_dataframe(df, key_columns=["id"])
    assert result["column_count"] == 3
    assert result["row_count"] == 4
    columns = {c["name"]: c for c in result["columns"]}
    assert columns["score"]["missing"] == 3
    assert columns["score"]["null_ratio"] == pytest.approx(0.75)
    assert columns["group"]["unique"] == 2
    assert result["key_uniqueness"]["id"] == 4
    assert any("missing" in w and "score" in w for w in result["warnings"])


def test_profile_flags_duplicate_rows_and_non_unique_key() -> None:
    df = pd.DataFrame({"id": [1, 1, 2], "v": [1.0, 1.0, 2.0]})
    result = profile_dataframe(df, key_columns=["id"])
    assert result["duplicate_rows"] == 1
    assert any("key" in w and "id" in w for w in result["warnings"])


def test_profile_numeric_summary_rounded_and_null_when_impossible() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "s": ["a", "b", "c"]})
    result = profile_dataframe(df)
    assert result["numeric_summary"]["x"]["mean"] == pytest.approx(2.0)
    assert result["numeric_summary"]["s"] is None
    assert isinstance(result["numeric_summary"]["x"]["std"], float)


def test_profile_csv_fails_closed_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        profile_csv(tmp_path / "nope.csv")


def test_profile_csv_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    result = profile_csv(path)
    assert result["row_count"] == 2
    assert result["column_count"] == 2
