import re
import shutil
import subprocess
from pathlib import Path

import pytest

XELATEX = shutil.which("xelatex")

pytestmark = pytest.mark.skipif(not XELATEX, reason="TeX toolchain (xelatex) not available")


def test_minimal_chinese_pdf_compiles_and_reports_pages(
    project_root: Path, tmp_path: Path
) -> None:
    template = project_root / "shared" / "templates" / "latex"
    assert template.is_dir(), "latex template missing"
    dest = tmp_path / "paper"
    shutil.copytree(template, dest)

    result = None
    for _ in range(2):
        result = subprocess.run(
            [XELATEX, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=dest,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]

    pdf = dest / "main.pdf"
    assert pdf.is_file(), "main.pdf not produced"

    log = (dest / "main.log").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\((\d+) page", log)
    assert match, "page count not found in xelatex log"
    assert int(match.group(1)) >= 1
    assert not re.search(r"undefined on input line", log), "unresolved reference remains"
