from pathlib import Path

import pytest

from cumcm_toolkit.pdf.inspect import inspect_pdf


def _raw_pdf_with_text(pages: list[str]) -> bytes:
    """Build a minimal valid PDF whose i-th page shows pages[i] as Helvetica text.

    A page whose entry is empty/whitespace gets no content stream and no font
    resource — a genuinely blank page. Built with raw PDF syntax only: pypdf
    can parse it and extract the text, and no reportlab / no external tools
    are needed (per the Task 5 fixture ruling).
    """
    n = len(pages)
    kids = " ".join(f"{3 + i} 0 R" for i in range(n))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",  # 1
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode("ascii"),  # 2
    ]
    font_index = 3 + n
    next_content = font_index + 1
    content_bodies: list[bytes] = []
    page_bodies: list[bytes] = []
    for i, text in enumerate(pages):
        if text.strip():
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content_bodies.append(
                ("BT /F1 12 Tf 50 100 Td (" + escaped + ") Tj ET").encode("ascii")
            )
            page_bodies.append(
                (
                    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
                    f"/Resources << /Font << /F1 {font_index} 0 R >> >> "
                    f"/Contents {next_content} 0 R >>"
                ).encode("ascii")
            )
            next_content += 1
        else:
            page_bodies.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>")
    objects.extend(page_bodies)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for body in content_bodies:
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body))
    objects.append(b"<< /Title (Inspect Fixture) >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % idx
        out += body
        out += b"\nendobj\n"
    xref_pos = len(out)
    size = len(objects) + 1
    out += b"xref\n0 %d\n" % size
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\n" % (size, len(objects))
    out += b"startxref\n%d\n%%%%EOF\n" % xref_pos
    return bytes(out)


def _make_pdf(path: Path, pages: list[str]) -> None:
    path.write_bytes(_raw_pdf_with_text(pages))


def test_inspect_reports_pages_and_blank(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    _make_pdf(pdf, ["hello", " ", "world"])
    report = inspect_pdf(pdf)
    assert report["pages"] == 3
    assert report["blank_pages"] == [2]
    assert report["status"] == "ok"
    assert report["errors"] == []
    # text pages 1 and 3 share one font resource: list is deduplicated
    assert report["fonts"] == [{"name": "/F1", "embedded": None}]
    assert isinstance(report["metadata"], dict)
    assert report["metadata"].get("/Title") == "Inspect Fixture"


def test_inspect_blank_pages_from_pypdf_writer(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as handle:
        writer.write(handle)
    report = inspect_pdf(pdf)
    assert report["pages"] == 3
    assert report["blank_pages"] == [1, 2, 3]
    assert report["fonts"] == []
    assert report["status"] == "ok"
    assert report["errors"] == []


def test_inspect_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        inspect_pdf(tmp_path / "nope.pdf")


def test_inspect_corrupt_file_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    with pytest.raises(ValueError):
        inspect_pdf(bad)
