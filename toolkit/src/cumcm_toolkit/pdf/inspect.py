from __future__ import annotations

import argparse
import json
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


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a PDF file")
    parser.add_argument("--pdf", type=Path, required=True, help="path to the PDF file")
    args = parser.parse_args()
    try:
        report = inspect_pdf(args.pdf)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(_json_safe(report), sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
