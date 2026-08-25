from __future__ import annotations

import hashlib
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
