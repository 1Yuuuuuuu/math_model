from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Word-boundary markers; a marker directly followed by "." or another word
# character (e.g. "TODO.png" as a filename) is not an unfinished placeholder.
_MARKERS = re.compile(r"\b(?:TODO|TBD|FIXME|待补充|待定)\b(?![.\w])")
_LABEL = re.compile(r"\\label\{([^}]+)\}")
_REF = re.compile(r"\\(?:ref|eqref|cref|Cref|autoref|pageref)\*?\{([^}]+)\}")
_INCLUDE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_CITE = re.compile(r"\\cite\{([^}]+)\}")
_BIB_ENTRY = re.compile(r"^@\w+\{([^,]+),", re.MULTILINE)


def _has_unescaped_percent(line: str) -> bool:
    """Heuristic: a line contains a raw % (not escaped by an odd run of
    backslashes). Whole-line comments (first non-space char is %) are skipped.
    Warning-level only: LaTeX would silently swallow the rest of the line."""
    if line.lstrip().startswith("%"):
        return False
    for position in [match.start() for match in re.finditer(r"%", line)]:
        backslashes = 0
        index = position - 1
        while index >= 0 and line[index] == "\\":
            backslashes += 1
            index -= 1
        if backslashes % 2 == 0:
            return True
    return False


def lint_paper(work_dir: Path) -> dict[str, object]:
    work_dir = work_dir.resolve()
    main = work_dir / "main.tex"
    if not main.is_file():
        raise ValueError(f"main.tex not found in {work_dir}")
    lines = main.read_text(encoding="utf-8", errors="replace").splitlines()
    issues: list[dict[str, object]] = []

    def add(severity: str, kind: str, line: int, message: str) -> None:
        issues.append({"severity": severity, "kind": kind, "line": line, "message": message})

    bib_path = work_dir / "bibliography.bib"
    bib_keys: set[str] = set()
    if bib_path.is_file():
        bib_keys = set(_BIB_ENTRY.findall(bib_path.read_text(encoding="utf-8", errors="replace")))

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
        for cited in _CITE.findall(line):
            for key in cited.split(","):
                key = key.strip()
                if key and key not in bib_keys:
                    add("warning", "cite_without_bib", index, f"cite without bib entry: {key}")
        if _has_unescaped_percent(line):
            add("warning", "unescaped_percent", index, "unescaped % truncates the rest of the line")

    for label in sorted(set(used) - set(defined)):
        add("error", "unresolved_ref", used[label], f"reference to undefined label: {label}")
    for label, line in defined.items():
        if label not in used:
            add("info", "unreferenced_label", line, f"label never referenced: {label}")

    status = "ok" if not any(i["severity"] == "error" for i in issues) else "failed"
    return {"status": status, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a CUMCM paper directory")
    parser.add_argument("--dir", type=Path, required=True, help="paper directory containing main.tex")
    args = parser.parse_args()
    try:
        report = lint_paper(args.dir)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
