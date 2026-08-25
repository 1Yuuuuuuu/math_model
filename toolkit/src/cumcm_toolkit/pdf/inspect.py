from __future__ import annotations

from pathlib import Path
from typing import Any

import pypdf


def inspect_pdf(pdf_path: Path) -> dict[str, object]:
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:
        raise ValueError(f"cannot read pdf {pdf_path}: {exc}") from exc
    pages = len(reader.pages)
    blank_pages: list[int] = []
    fonts: dict[str, object] = {}
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if not text:
            blank_pages.append(index)
        resources = page.get("/Resources")
        if resources is not None:
            font_dict = resources.get("/Font")
            if isinstance(font_dict, dict):
                for name in font_dict:
                    fonts.setdefault(str(name), {"embedded": None})
    return {
        "status": "ok",
        "pages": pages,
        "blank_pages": blank_pages,
        "fonts": [{"name": name, "embedded": info["embedded"]} for name, info in fonts.items()],
        "metadata": dict(reader.metadata or {}),
        "errors": [],
    }
