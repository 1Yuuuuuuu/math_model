import json
from pathlib import Path

import pytest

from cumcm_toolkit.results.export import export_csv, export_json, export_latex_table


def test_export_json_roundtrip(tmp_path: Path) -> None:
    path = export_json({"a": 1, "b": [1.5, 2.5]}, tmp_path / "out.json")
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": [1.5, 2.5]}


def test_export_json_rejects_nan(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_json({"a": float("nan")}, tmp_path / "bad.json")


def test_export_csv_order_and_content(tmp_path: Path) -> None:
    path = export_csv([{"b": 1, "a": 2}, {"b": 3, "a": 4}], tmp_path / "out.csv")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "b,a"
    assert lines[1] == "1,2"


def test_export_latex_table_escapes(tmp_path: Path) -> None:
    path = export_latex_table(
        [{"metric": "rmse", "value": 0.5}], tmp_path / "t.tex", caption="结果"
    )
    text = path.read_text(encoding="utf-8")
    assert "metric" in text and "rmse" in text
    assert "caption" in text


def test_export_empty_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_csv([], tmp_path / "empty.csv")
