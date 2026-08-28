from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Any


def bib_key_for_source_id(source_id: str) -> str:
    """Derive the deterministic BibTeX key for a literature source id.

    Key = ``src_`` + sha256(source_id)[:8]. The same derivation is used by
    ``bibtex_entry``/``generate_bibliography`` so callers (e.g.
    ``citation_check``) can bridge document-side ``\\cite{<bib key>}`` back to
    the citation link's ``source_id``.
    """
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
    return f"src_{digest[:8]}"


def _bib_key(source: dict[str, Any]) -> str:
    return bib_key_for_source_id(source["source_id"])


def _escape(value: object) -> str:
    return str(value).replace("&", "\\&").replace("%", "\\%").replace("#", "\\#")


def bibtex_entry(source: dict[str, Any]) -> str:
    key = _bib_key(source)
    fields: dict[str, str] = {}
    if source.get("title"):
        fields["title"] = _escape(source["title"])
    if source.get("authors"):
        fields["author"] = " and ".join(_escape(a) for a in source["authors"])
    if source.get("year"):
        fields["year"] = str(source["year"])
    venue = source.get("venue_or_repository")
    kind = "article" if venue else "misc"
    if venue:
        fields["journal"] = _escape(venue)
    identifiers = source.get("identifiers") or {}
    if identifiers.get("doi"):
        fields["doi"] = identifiers["doi"]
    if source.get("canonical_url"):
        fields["url"] = source["canonical_url"]
    lines = [f"@{kind}{{{key},"]
    for name, value in fields.items():
        lines.append(f"  {name} = {{{value}}},")
    lines.append("}")
    return "\n".join(lines)


def generate_bibliography(sources: list[dict[str, Any]]) -> str:
    header = "% 由 bibliography 工具从已批准 literature-source 生成。\n"
    entries = [bibtex_entry(s) for s in sorted(sources, key=lambda s: s["source_id"])]
    return header + "\n".join(entries) + "\n"


def _reject_nonstandard_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BibTeX text from approved literature sources")
    parser.add_argument("--sources", required=True, help="JSON array of literature-source records")
    args = parser.parse_args()
    try:
        sources = json.loads(args.sources, parse_constant=_reject_nonstandard_json_constant)
        if not isinstance(sources, list):
            raise ValueError("--sources must be a JSON array")
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                raise ValueError(f"--sources item {index} must be an object")
            if "source_id" not in source:
                raise ValueError(f"--sources item {index} missing source_id")
        bibtex = generate_bibliography(sources)
        result: dict[str, object] = {"status": "ok", "bibtex": bibtex}
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
