from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from cumcm_toolkit.utils.numbers import is_finite_number, to_python_scalar


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _check_finite(value: object, where: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _check_finite(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_finite(item, f"{where}[{index}]")
    elif value is None or isinstance(value, str):
        return
    elif not is_finite_number(value):
        raise ValueError(f"non-finite number in {where}: {value}")


def export_json(data: object, path: Path) -> Path:
    _check_finite(data, "root")
    try:
        path.write_text(
            json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False, default=to_python_scalar),
            encoding="utf-8",
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot serialize json to {path}: {exc}") from exc
    return path


def export_csv(rows: list[dict[str, object]], path: Path) -> Path:
    if not rows:
        raise ValueError("cannot export empty rows to csv")
    columns = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _latex_escape(value: object) -> str:
    text = str(value)
    return text.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def export_latex_table(
    rows: list[dict[str, object]], path: Path, *, caption: str = ""
) -> Path:
    if not rows:
        raise ValueError("cannot export empty rows to latex table")
    columns = list(rows[0].keys())
    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        f"\\caption{{{_latex_escape(caption)}}}",
        "\\begin{tabular}{" + "l" * len(columns) + "}",
        "\\toprule",
        " & ".join(_latex_escape(c) for c in columns) + r" \\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(row.get(c, "")) for c in columns) + r" \\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def save_figure(fig: Any, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    try:
        fig.savefig(path, bbox_inches="tight")
    except Exception as exc:
        raise ValueError(f"cannot save figure to {path}: {exc}") from exc
    return path
