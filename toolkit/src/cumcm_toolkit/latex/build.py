from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def _find(name: str) -> str | None:
    try:
        return shutil.which(name)
    except TypeError:
        # Fail closed on a broken availability probe (e.g. a mock that
        # accepts no arguments): treat as "not found", never crash.
        return None


def build_paper(
    work_dir: Path, *, passes: int = 2, timeout: float = 600.0
) -> dict[str, object]:
    xelatex = _find("xelatex")
    if xelatex is None:
        raise ValueError("xelatex not found on PATH")
    work_dir = work_dir.resolve()
    main = work_dir / "main.tex"
    if not main.is_file():
        raise ValueError(f"main.tex not found in {work_dir}")

    xelatex_cmd = [xelatex, "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
    with_bibtex = (work_dir / "bibliography.bib").is_file()
    bibtex = _find("bibtex") if with_bibtex else None

    errors: list[str] = []
    warnings: list[str] = []
    if with_bibtex and bibtex is None:
        warnings.append(
            "bibtex not found on PATH; skipping the bibtex pass "
            "(citations may stay unresolved; xelatex-only is the fallback)"
        )

    # Pass sequence: xelatex, then (bibtex when bibliography.bib exists), then
    # `passes` more xelatex runs (xelatex → bibtex → xelatex → xelatex).
    sequence: list[tuple[int, list[str]]] = [(1, xelatex_cmd)]
    next_pass = 2
    if with_bibtex and bibtex is not None:
        sequence.append((next_pass, [bibtex, "main"]))
        next_pass += 1
    for _ in range(passes):
        sequence.append((next_pass, xelatex_cmd))
        next_pass += 1

    failed_pass: int | None = None
    final_result: subprocess.CompletedProcess[str] | None = None
    for pass_no, argv in sequence:
        try:
            result = subprocess.run(
                argv,
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"timeout after {timeout}s")
            failed_pass = pass_no
            break
        final_result = result
        if result.returncode != 0:
            failed_pass = pass_no
            break

    log_path = work_dir / "main.log"
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

    # Fail closed: any failed pass, timeout, or leftover undefined reference
    # (after all passes) makes the build failed. The report keeps the
    # undefined_references detail for diagnosis.
    ok = (
        final_result is not None
        and final_result.returncode == 0
        and not errors
        and not undefined_references
    )
    return {
        "status": "ok" if ok else "failed",
        "passes": passes,
        "errors": errors,
        "warnings": warnings,
        "pages": pages,
        "undefined_references": undefined_references,
        "failed_pass": failed_pass,
        "pdf_path": work_dir / "main.pdf",
        "log_path": log_path,
    }
