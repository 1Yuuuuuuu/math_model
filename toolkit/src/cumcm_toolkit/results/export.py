from __future__ import annotations

import argparse
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


def _require_rows(value: object, where: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be a JSON array of row objects")
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValueError(f"{where} item {index} must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Export results to json, csv, or a LaTeX table")
    parser.add_argument("--json", dest="json_data", default=None, help="JSON data to export as a file")
    parser.add_argument("--csv", dest="csv_rows", default=None, help="JSON array of row objects to export as csv")
    parser.add_argument("--latex", action="store_true", help="export --rows as a LaTeX table")
    parser.add_argument("--rows", dest="latex_rows", default=None, help="JSON array of row objects for the LaTeX table")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--caption", default="")
    args = parser.parse_args()
    try:
        modes = [m for m in (args.json_data, args.csv_rows, args.latex) if m not in (None, False)]
        if len(modes) != 1:
            raise ValueError("exactly one of --json, --csv, --latex is required")
        if args.json_data is not None:
            data = json.loads(args.json_data, parse_constant=_reject_nonstandard_json_constant)
            path = export_json(data, args.out)
            fmt = "json"
        elif args.csv_rows is not None:
            rows = json.loads(args.csv_rows, parse_constant=_reject_nonstandard_json_constant)
            path = export_csv(_require_rows(rows, "--csv"), args.out)
            fmt = "csv"
        else:
            if args.latex_rows is None:
                raise ValueError("--latex requires --rows")
            rows = json.loads(args.latex_rows, parse_constant=_reject_nonstandard_json_constant)
            path = export_latex_table(_require_rows(rows, "--rows"), args.out, caption=args.caption)
            fmt = "latex"
        result: dict[str, object] = {"status": "ok", "path": str(path.resolve()), "format": fmt}
    except (TypeError, ValueError, KeyError, AttributeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
