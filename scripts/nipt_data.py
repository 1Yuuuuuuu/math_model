"""Load the 2025-C NIPT attachment into structured DataFrames.

Reads both sheets of the official xlsx (sheet1=male, sheet2=female) using
pandas + openpyxl-independent stdlib conversion cached to CSVs under a
configurable data dir. Provides clean columns for the four problems.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

M_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

DEFAULT_XLSX = Path(r"E:\国赛论文对比\官网题目\C题\附件.xlsx")

# Column names per the problem appendix (A-AE, 31 cols)
COLUMNS = [
    "sample_id", "mother_id", "age", "height", "weight", "last_menstrual",
    "ivf", "test_date", "draw_no", "gestational_week", "bmi",
    "total_reads", "mapped_ratio", "dup_ratio", "unique_reads", "gc_content",
    "z13", "z18", "z21", "zx", "zy", "y_conc", "x_conc",
    "gc13", "gc18", "gc21", "filtered_ratio", "aneuploidy",
    "gravidity", "parity", "health",
]


def _cell_text(c: ET.Element, shared: list[str]) -> str:
    t = c.get("t")
    v = c.find(M_NS + "v")
    istr = c.find(M_NS + "is")
    if t == "s" and v is not None:
        return shared[int(v.text)]
    if t == "inlineStr" and istr is not None:
        return "".join(x.text or "" for x in istr.iter(M_NS + "t"))
    if v is not None:
        return v.text
    return ""


def _col_index(ref: str) -> int:
    idx = 0
    for ch in ref:
        if ch.isalpha():
            idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _read_sheet(z: zipfile.ZipFile, sheet_name: str) -> pd.DataFrame:
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(M_NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(M_NS + "t")))
    root = ET.fromstring(z.read(sheet_name))
    rows: list[list[str]] = []
    for row in root.findall(".//" + M_NS + "row"):
        cells: dict[int, str] = {}
        for c in row.findall(M_NS + "c"):
            cells[_col_index(c.get("r", "A"))] = _cell_text(c, shared)
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(padded[1:], columns=COLUMNS[: width])
    return df


def parse_week(s: object) -> float | None:
    m = re.match(r"(\d+)w\+(\d+)", str(s))
    if m:
        return int(m.group(1)) + int(m.group(2)) / 7
    return None


@dataclass
class NIPTData:
    male: pd.DataFrame
    female: pd.DataFrame


def load_nipt(xlsx: Path = DEFAULT_XLSX) -> NIPTData:
    with zipfile.ZipFile(xlsx) as z:
        male = _read_sheet(z, "xl/worksheets/sheet1.xml")
        female = _read_sheet(z, "xl/worksheets/sheet2.xml")
    for df in (male, female):
        df["week"] = df["gestational_week"].map(parse_week)
        for col in ("age", "height", "weight", "bmi", "y_conc", "x_conc", "zy",
                    "z13", "z18", "z21", "zx", "gc13", "gc18", "gc21", "gc_content"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return NIPTData(male=male, female=female)


if __name__ == "__main__":
    data = load_nipt()
    print("male:", data.male.shape, "female:", data.female.shape)
    print("male Y-conc sample:", data.male[["mother_id", "week", "bmi", "y_conc"]].head(5).to_string())
    print("male Y>=4%:", int((data.male["y_conc"] >= 0.04).sum()), "/", len(data.male))
