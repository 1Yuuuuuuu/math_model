import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.pdf.inspect import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def _raw_pdf_with_text(pages: list[str]) -> bytes:
    """Minimal valid PDF; reused pattern from test_inspect.py."""
    n = len(pages)
    kids = " ".join(f"{3 + i} 0 R" for i in range(n))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode("ascii"),
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


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.pdf.inspect", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def test_cli_success_subprocess(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(_raw_pdf_with_text(["hello", " ", "world"]))
    proc = _run_cli("--pdf", str(pdf))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "ok"
    assert report["pages"] == 3
    assert report["blank_pages"] == [2]
    assert report["fonts"] == [{"name": "/F1"}]
    assert report["metadata"].get("/Title") == "Inspect Fixture"


def test_cli_missing_file_fails_closed(tmp_path: Path) -> None:
    proc = _run_cli("--pdf", str(tmp_path / "nope.pdf"))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert "nope.pdf" in payload["error"]


def test_cli_corrupt_file_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    proc = _run_cli("--pdf", str(bad))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_pypdf_writer_pdf_success(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as handle:
        writer.write(handle)
    proc = _run_cli("--pdf", str(pdf))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["pages"] == 1
    assert report["status"] == "ok"
