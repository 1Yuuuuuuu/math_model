from __future__ import annotations

from pathlib import Path

import pypdf


def inspect_pdf(pdf_path: Path) -> dict[str, object]:
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:
        raise ValueError(f"cannot read pdf {pdf_path}: {exc}") from exc
    pages = len(reader.pages)
    blank_pages: list[int] = []
    fonts: dict[str, None] = {}
    errors: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted_ok = True
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:
            # A failed extraction is a defect, not a blank page.
            errors.append(f"page {index} text extraction failed: {exc}")
            extracted_ok = False
            text = ""
        if extracted_ok and not text:
            blank_pages.append(index)
        resources = page.get("/Resources")
        if resources is not None:
            font_dict = resources.get("/Font")
            if isinstance(font_dict, dict):
                for name in font_dict:
                    fonts.setdefault(str(name), None)
    return {
        # Font embedding detection is not implemented reliably; report the
        # font names only instead of pretending (no "embedded" field).
        "status": "failed" if errors else "ok",
        "pages": pages,
        "blank_pages": blank_pages,
        "fonts": [{"name": name} for name in fonts],
        "metadata": dict(reader.metadata or {}),
        "errors": errors,
    }
