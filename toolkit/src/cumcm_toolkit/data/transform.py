from __future__ import annotations

from typing import Any

import pandas as pd


def transform_dataframe(
    df: pd.DataFrame, steps: list[dict[str, object]]
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    out = df.copy()
    warnings: list[str] = []
    applied = 0

    def missing_columns(columns: list[str]) -> list[str]:
        return [c for c in columns if c not in out.columns]

    def _require_column_list(step: dict[str, object], key: str) -> list[str]:
        value = step.get(key, [])
        if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
            raise ValueError(f"step {step.get('op')}: {key} must be a list of strings")
        return list(value)

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {index}: must be an object")
        op = step.get("op")
        if not isinstance(op, str):
            raise ValueError(f"step {index}: op must be a string")
        if op == "drop_columns":
            columns = _require_column_list(step, "columns")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"drop_columns: missing columns {missing}")
            out = out.drop(columns=[c for c in columns if c in out.columns], errors="ignore")
        elif op == "drop_missing":
            subset = _require_column_list(step, "subset")
            if subset:
                missing = missing_columns(subset)
                if missing:
                    warnings.append(f"drop_missing: missing columns {missing}")
                present = [c for c in subset if c in out.columns]
                if present:
                    out = out.dropna(subset=present)
            else:
                out = out.dropna(subset=None)
        elif op == "fill_missing":
            columns = _require_column_list(step, "columns")
            value = step.get("value")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"fill_missing: missing columns {missing}")
            for column in [c for c in columns if c in out.columns]:
                out[column] = out[column].fillna(value)
        elif op == "normalize":
            columns = _require_column_list(step, "columns")
            method = step.get("method", "minmax")
            if method not in {"minmax", "zscore"}:
                raise ValueError(f"step {index}: unknown normalize method {method}")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"normalize: missing columns {missing}")
            for column in [c for c in columns if c in out.columns]:
                if not pd.api.types.is_numeric_dtype(out[column].dtype):
                    raise ValueError(f"step {index}: column {column} is not numeric")
                clean = pd.to_numeric(out[column], errors="coerce")
                if method == "minmax":
                    lo, hi = clean.min(), clean.max()
                    if pd.isna(lo) or lo == hi:
                        warnings.append(f"normalize: constant or empty column {column}")
                        out[column] = out[column].where(out[column].isna(), 0.0)
                    else:
                        out[column] = (clean - lo) / (hi - lo)
                else:
                    mean, std = clean.mean(), clean.std(ddof=0)
                    if pd.isna(std) or std == 0:
                        warnings.append(f"normalize: constant or empty column {column}")
                        out[column] = out[column].where(out[column].isna(), 0.0)
                    else:
                        out[column] = (clean - mean) / std
        elif op == "to_datetime":
            columns = _require_column_list(step, "columns")
            for column in columns:
                if column not in out.columns:
                    warnings.append(f"to_datetime: missing column {column}")
                    continue
                out[column] = pd.to_datetime(out[column], errors="raise")
        elif op == "cast":
            columns = _require_column_list(step, "columns")
            dtype = step.get("dtype")
            if not isinstance(dtype, str):
                raise ValueError(f"step {index}: cast requires dtype")
            for column in columns:
                if column not in out.columns:
                    warnings.append(f"cast: missing column {column}")
                    continue
                try:
                    out[column] = out[column].astype(dtype)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"step {index}: cannot cast {column} to {dtype}: {exc}") from exc
        else:
            raise ValueError(f"step {index}: unknown op {op}")
        applied += 1

    return out, {"steps_applied": applied, "warnings": sorted(set(warnings))}
