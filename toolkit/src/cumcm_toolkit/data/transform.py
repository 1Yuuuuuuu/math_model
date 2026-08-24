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

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {index}: must be an object")
        op = step.get("op")
        if not isinstance(op, str):
            raise ValueError(f"step {index}: op must be a string")
        if op == "drop_columns":
            columns = list(step.get("columns", []))
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"drop_columns: missing columns {missing}")
            out = out.drop(columns=[c for c in columns if c in out.columns], errors="ignore")
        elif op == "drop_missing":
            subset = step.get("subset")
            subset = list(subset) if subset else None
            if subset:
                missing = missing_columns(subset)
                if missing:
                    warnings.append(f"drop_missing: missing columns {missing}")
                subset = [c for c in subset if c in out.columns]
            if subset:
                out = out.dropna(subset=subset)
        elif op == "fill_missing":
            columns = list(step.get("columns", []))
            value = step.get("value")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"fill_missing: missing columns {missing}")
            for column in [c for c in columns if c in out.columns]:
                out[column] = out[column].fillna(value)
        elif op == "normalize":
            columns = list(step.get("columns", []))
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
                        out[column] = 0.0
                    else:
                        out[column] = (clean - lo) / (hi - lo)
                else:
                    mean, std = clean.mean(), clean.std(ddof=0)
                    if pd.isna(std) or std == 0:
                        warnings.append(f"normalize: constant or empty column {column}")
                        out[column] = 0.0
                    else:
                        out[column] = (clean - mean) / std
        elif op == "to_datetime":
            for column in list(step.get("columns", [])):
                if column not in out.columns:
                    warnings.append(f"to_datetime: missing column {column}")
                    continue
                out[column] = pd.to_datetime(out[column], errors="raise")
        elif op == "cast":
            for column in list(step.get("columns", [])):
                if column not in out.columns:
                    warnings.append(f"cast: missing column {column}")
                    continue
                dtype = step.get("dtype")
                if not isinstance(dtype, str):
                    raise ValueError(f"step {index}: cast requires dtype")
                try:
                    out[column] = out[column].astype(dtype)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"step {index}: cannot cast {column} to {dtype}: {exc}") from exc
        else:
            raise ValueError(f"step {index}: unknown op {op}")
        applied += 1

    return out, {"steps_applied": applied, "warnings": sorted(set(warnings))}
