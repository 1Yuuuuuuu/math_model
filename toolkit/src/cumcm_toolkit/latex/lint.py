from __future__ import annotations

import re
from pathlib import Path

_MARKERS = re.compile(r"TODO|待补充|FIXME|TBD|待定")
_LABEL = re.compile(r"\\label\{([^}]+)\}")
_REF = re.compile(r"\\(?:ref|eqref)\{([^}]+)\}")
_INCLUDE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


def lint_paper(work_dir: Path) -> dict[str, object]:
    work_dir = work_dir.resolve()
    main = work_dir / "main.tex"
    if not main.is_file():
        raise ValueError(f"main.tex not found in {work_dir}")
    lines = main.read_text(encoding="utf-8", errors="replace").splitlines()
    issues: list[dict[str, object]] = []

    def add(severity: str, kind: str, line: int, message: str) -> None:
        issues.append({"severity": severity, "kind": kind, "line": line, "message": message})

    defined: dict[str, int] = {}
    used: dict[str, int] = {}  # label -> first line where it is referenced
    for index, line in enumerate(lines, start=1):
        for label, match in ((m.group(1), m) for m in _LABEL.finditer(line)):
            if label in defined:
                add("error", "duplicate_label", index, f"duplicate label: {label} (first at line {defined[label]})")
            else:
                defined[label] = index
        for label in _REF.findall(line):
            used.setdefault(label, index)
        if _MARKERS.search(line):
            add("error", "placeholder", index, f"unfinished marker: {line.strip()[:60]}")
        for image in _INCLUDE.findall(line):
            candidate = work_dir / image
            if not candidate.is_file():
                add("error", "missing_image", index, f"image not found: {image}")

    for label in sorted(set(used) - set(defined)):
        add("error", "unresolved_ref", used[label], f"reference to undefined label: {label}")
    for label, line in defined.items():
        if label not in used:
            add("info", "unreferenced_label", line, f"label never referenced: {label}")

    status = "ok" if not any(i["severity"] == "error" for i in issues) else "failed"
    return {"status": status, "issues": issues}
