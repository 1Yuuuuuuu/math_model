from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def build_paper(
    work_dir: Path, *, passes: int = 2, timeout: float = 600.0
) -> dict[str, object]:
    try:
        xelatex = shutil.which("xelatex")
    except TypeError:
        # Fail closed on a broken availability probe (e.g. a mock that
        # accepts no arguments): treat as "not found", never crash.
        xelatex = None
    if xelatex is None:
        raise ValueError("xelatex not found on PATH")
    work_dir = work_dir.resolve()
    main = work_dir / "main.tex"
    if not main.is_file():
        raise ValueError(f"main.tex not found in {work_dir}")
    final_result: subprocess.CompletedProcess[str] | None = None
    for _ in range(passes):
        final_result = subprocess.run(
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    log_path = work_dir / "main.log"
    errors: list[str] = []
    warnings: list[str] = []
    pages: int | None = None
    undefined_references: list[str] = []
    if log_path.is_file():
        log = log_path.read_text(encoding="utf-8", errors="replace")
        for line in log.splitlines():
            if line.startswith("! "):
                errors.append(line)
            if "LaTeX Warning" in line:
                warnings.append(line.strip())
            if "undefined on input line" in line:
                undefined_references.append(line.strip())
        match = re.search(r"\((\d+) page", log)
        if match:
            pages = int(match.group(1))
    ok = final_result is not None and final_result.returncode == 0
    return {
        "status": "ok" if ok else "failed",
        "passes": passes,
        "errors": errors,
        "warnings": warnings,
        "pages": pages,
        "undefined_references": undefined_references,
        "pdf_path": work_dir / "main.pdf",
        "log_path": log_path,
    }
