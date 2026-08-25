from __future__ import annotations

import re
from typing import Any

from cumcm_toolkit.latex.bibliography import bib_key_for_source_id

_CITE = re.compile(r"\\cite\{([^}]+)\}")


def _cited_keys(tex_text: str) -> set[str]:
    keys: set[str] = set()
    for match in _CITE.finditer(tex_text):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def _bib_entries(bib_text: str) -> set[str]:
    return set(re.findall(r"^@\w+\{([^,]+),", bib_text, re.MULTILINE))


def citation_check(
    tex_text: str,
    bib_text: str,
    citations: list[dict[str, Any]],
    approved_source_ids: set[str],
) -> dict[str, object]:
    cited = _cited_keys(tex_text)
    entries = _bib_entries(bib_text)
    citation_source_ids = {c["source_id"] for c in citations}
    # generate_bibliography derives BibTeX keys from the source_id
    # (src_<sha256-8>), so a citation's document-side key is its source_id
    # itself OR the derived key. Accept both namespaces when matching
    # cite<->bib<->citation-link; every rule below still must hold
    # (fail-closed preserved).
    known_keys = citation_source_ids | {
        bib_key_for_source_id(source_id) for source_id in citation_source_ids
    }

    missing_bibtex = sorted(cited - entries)
    unapproved_sources = sorted(source for source in citation_source_ids if source not in approved_source_ids)
    uncited_entries = sorted((entries - cited) | (entries - known_keys))
    unmatched_citations = sorted(cited - known_keys)
    # Orphaned direction: a citation link whose source has no bib entry at all.
    # The bib may key the entry by the source_id itself or by its derived bib
    # key, so a source is orphaned only when NEITHER namespace is present
    # (reporting the source_id keeps the report actionable).
    orphaned_citations = sorted(
        source_id
        for source_id in citation_source_ids
        if source_id not in entries and bib_key_for_source_id(source_id) not in entries
    )
    errors: list[str] = []
    if missing_bibtex:
        errors.append(f"cite without bib entry: {missing_bibtex}")
    if unapproved_sources:
        errors.append(f"citation from unapproved source: {unapproved_sources}")
    if uncited_entries:
        errors.append(f"bib entry uncited or without citation link: {uncited_entries}")
    if unmatched_citations:
        errors.append(f"cite without citation link: {unmatched_citations}")
    if orphaned_citations:
        errors.append(f"citation link without bib entry: {orphaned_citations}")
    return {
        "status": "ok" if not errors else "failed",
        "missing_bibtex": missing_bibtex,
        "unapproved_sources": unapproved_sources,
        "uncited_entries": uncited_entries,
        "unmatched_citations": unmatched_citations,
        "orphaned_citations": orphaned_citations,
        "errors": errors,
    }
