"""Literature deduplication rule engine (single source of truth).

The rules in this module are the Python-side contract for the Phase 0A
literature pipeline:

- deterministic grouping of candidate records (DOI → normalized title →
  normalized URL, first available field only), byte-for-byte identical to the
  reference implementation in ``tests/knowledge/test_literature_knowledge.py``
  (the reference test code IS the rule contract);
- conflict flagging per ``shared/knowledge/literature/deduplication.md``:
  mark only — never merge, never pick a "better" record, never repair
  metadata; conflicted groups stay candidates for human review.

The TypeScript ``literature-tools`` plugin forwards candidate arrays to this
module's CLI (``python -m cumcm_toolkit.literature.rules --group <json>``) and
never reimplements the rules.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata


def normalize_title(title: str) -> str:
    """NFKC + lowercase, then drop every non-word character and underscore.

    Identical to the reference ``_normalize_title`` in
    ``tests/knowledge/test_literature_knowledge.py``.
    """
    text = unicodedata.normalize("NFKC", title.lower())
    return re.sub(r"[\W_]+", "", text)


def _group_key(record: dict) -> str | None:
    """First available identifier: DOI → normalized title → normalized URL."""
    if record.get("doi"):
        return f"doi:{record['doi'].lower()}"
    if record.get("title"):
        return f"title:{normalize_title(record['title'])}"
    if record.get("url"):
        return f"url:{re.sub(r'#.*$', '', record['url']).rstrip('/')}"
    return None


def group_candidates(records: list[dict]) -> dict[str, list[str]]:
    """Deterministic grouping identical to the reference implementation.

    Group key → list of record ids. Records with no doi/title/url are skipped
    (they stay ungrouped for later human completion).
    """
    groups: dict[str, list[str]] = {}
    for record in records:
        key = _group_key(record)
        if key is None:
            continue
        groups.setdefault(key, []).append(record["id"])
    return groups


def _authors_differ(group: list[dict]) -> bool:
    """True when the author lists are not identical across the group.

    Per deduplication.md, order differences, name differences, and a record
    missing authors while another has them all count as mismatch.
    """
    tuples = [
        tuple(record["authors"])
        for record in group
        if isinstance(record.get("authors"), (list, tuple)) and len(record["authors"]) > 0
    ]
    if len(set(tuples)) > 1:
        return True
    if tuples and any(
        not (isinstance(record.get("authors"), (list, tuple)) and len(record["authors"]) > 0)
        for record in group
    ):
        return True
    return False


def conflict_flags(group: list[dict]) -> list[str]:
    """Mark metadata conflicts inside one group; NEVER merge / pick / repair.

    Returns a deterministic, deduplicated list of flag strings:

    - ``authors_mismatch`` — author lists differ (order, names, or missing);
    - ``year_mismatch`` — years differ;
    - ``venue_mismatch`` — ``venue_or_repository`` differs;
    - ``same_doi_diff_metadata`` — every record shares one (case-insensitive)
      DOI yet titles or author lists differ (possible version/error).

    Empty list = no conflict; single-record groups never conflict.
    """
    flags: list[str] = []
    if len(group) < 2:
        return flags

    if _authors_differ(group):
        flags.append("authors_mismatch")

    years = {record["year"] for record in group if record.get("year") is not None}
    if len(years) > 1:
        flags.append("year_mismatch")

    venues = {
        record["venue_or_repository"]
        for record in group
        if record.get("venue_or_repository") not in (None, "")
    }
    if len(venues) > 1:
        flags.append("venue_mismatch")

    dois = {str(record["doi"]).lower() for record in group if record.get("doi")}
    if all(record.get("doi") for record in group) and len(dois) == 1:
        titles = {normalize_title(record["title"]) for record in group if record.get("title")}
        title_diff = len(titles) > 1 or (
            titles and any(not record.get("title") for record in group)
        )
        if title_diff or _authors_differ(group):
            flags.append("same_doi_diff_metadata")

    return flags


def _fail(message: str) -> int:
    print(
        json.dumps(
            {"status": "failed", "error": message},
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
    )
    return 1


def main() -> int:
    """CLI: ``python -m cumcm_toolkit.literature.rules --group <json>``.

    Success: single-line JSON ``{"groups": {...}, "conflicts": {...}}`` on
    stdout, exit 0 (``sort_keys=True, ensure_ascii=True, allow_nan=False``).
    Failure: ``{"status": "failed", "error": ...}`` on stdout, exit 1.
    Argparse-level failure (missing ``--group``) exits 2 with empty stdout and
    usage on stderr — the fail-closed I-1 contract the TS bridge relies on.
    """
    parser = argparse.ArgumentParser(description="Literature deduplication rule engine")
    parser.add_argument(
        "--group",
        required=True,
        help="JSON array of candidate records (each with id and doi/title/url)",
    )
    args = parser.parse_args()

    try:
        records = json.loads(args.group)
        if not isinstance(records, list):
            raise ValueError("--group must be a JSON array of candidate records")

        by_key: dict[str, list[dict]] = {}
        for record in records:
            key = _group_key(record)
            if key is None:
                continue
            by_key.setdefault(key, []).append(record)

        groups = {key: [record["id"] for record in members] for key, members in by_key.items()}
        conflicts: dict[str, list[str]] = {}
        for key, members in by_key.items():
            flags = conflict_flags(members)
            if flags:
                conflicts[key] = flags
    except Exception as exc:
        return _fail(str(exc))

    print(
        json.dumps(
            {"groups": groups, "conflicts": conflicts},
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
