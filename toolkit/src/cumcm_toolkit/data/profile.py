from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def profile_dataframe(
    df: pd.DataFrame, *, key_columns: list[str] | None = None
) -> dict[str, object]:
    warnings: list[str] = []
    columns = []
    numeric_summary: dict[str, object] = {}
    for name in df.columns:
        series = df[name]
        missing = int(series.isna().sum())
        row_count = len(df)
        entry: dict[str, object] = {
            "name": str(name),
            "dtype": str(series.dtype),
            "missing": missing,
            "unique": int(series.nunique()),
            "null_ratio": round(missing / row_count, 6) if row_count else 0.0,
        }
        columns.append(entry)
        if missing == row_count:
            _warn(warnings, f"column all missing: {name}")
        elif missing / row_count > 0.5:
            _warn(warnings, f"column mostly missing: {name}")
        if pd.api.types.is_numeric_dtype(series.dtype) and missing != row_count:
            clean = pd.to_numeric(series, errors="coerce").dropna()
            if len(clean):
                numeric_summary[str(name)] = {
                    "min": round(float(clean.min()), 6),
                    "max": round(float(clean.max()), 6),
                    "mean": round(float(clean.mean()), 6),
                    "std": round(float(clean.std(ddof=0)), 6),
                }
            else:
                numeric_summary[str(name)] = None
        else:
            numeric_summary[str(name)] = None

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        _warn(warnings, f"duplicate rows: {duplicate_rows}")
    key_uniqueness: dict[str, int] = {}
    if key_columns:
        for key in key_columns:
            if key not in df.columns:
                _warn(warnings, f"key column missing: {key}")
                continue
            unique_count = int(df[key].nunique())
            key_uniqueness[key] = unique_count
            if unique_count != len(df):
                _warn(warnings, f"key not unique: {key}")

    return {
        "column_count": int(df.shape[1]),
        "row_count": int(df.shape[0]),
        "columns": columns,
        "duplicate_rows": duplicate_rows,
        "numeric_summary": numeric_summary,
        "key_uniqueness": key_uniqueness,
        "warnings": warnings,
    }


def profile_csv(path: Path, *, key_columns: list[str] | None = None, **kwargs: Any) -> dict[str, object]:
    try:
        df = pd.read_csv(path, **kwargs)
    except Exception as exc:
        raise ValueError(f"cannot read csv {path}: {exc}") from exc
    return profile_dataframe(df, key_columns=key_columns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile a CSV data file")
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--key-columns", default="", help="comma-separated key columns")
    args = parser.parse_args()
    try:
        result = profile_csv(
            args.path, key_columns=[c for c in args.key_columns.split(",") if c]
        )
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
