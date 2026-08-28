"""Rule engine tests for `cumcm_toolkit.literature.rules`.

Aligned with the reference implementation in
`tests/knowledge/test_literature_knowledge.py` (`_normalize_title` /
`group_candidates`): the reference test code is the rule contract, so these
tests assert the exact same normalization and grouping behavior, plus the
conflict-flag rules from `shared/knowledge/literature/deduplication.md`
(mark only, never merge / pick / repair).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.literature.rules import (
    conflict_flags,
    group_candidates,
    main as cli_main,
    normalize_title,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# normalize_title (reference `_normalize_title`)
# ---------------------------------------------------------------------------


def test_normalize_title_strips_case_space_and_punctuation() -> None:
    assert normalize_title("A Novel Method") == "anovelmethod"
    assert normalize_title("A  Novel  Method!") == "anovelmethod"
    assert normalize_title("Deep-Learning_Approaches.") == "deeplearningapproaches"


def test_normalize_title_nfkc_folds_composed_and_decomposed_forms() -> None:
    # "Café" (precomposed é) and "Cafe\u0301" (e + combining acute) both
    # normalize to the same NFC form under NFKC.
    assert normalize_title("Café Study") == normalize_title("Cafe\u0301 Study")
    assert normalize_title("Café Study") == "caféstudy"


# ---------------------------------------------------------------------------
# group_candidates (reference `group_candidates`, byte-for-byte behavior)
# ---------------------------------------------------------------------------


def test_dedup_groups_by_doi_case_insensitive() -> None:
    groups = group_candidates(
        [
            {"id": "a", "doi": "10.1000/ABC"},
            {"id": "b", "doi": "10.1000/abc"},
            {"id": "c", "doi": "10.1000/XYZ"},
        ]
    )
    assert set(groups["doi:10.1000/abc"]) == {"a", "b"}
    assert set(groups["doi:10.1000/xyz"]) == {"c"}


def test_dedup_groups_by_normalized_title() -> None:
    groups = group_candidates(
        [
            {"id": "a", "title": "A Novel Method"},
            {"id": "b", "title": "A  Novel  Method!"},
            {"id": "c", "title": "A Different Method"},
        ]
    )
    assert set(groups["title:anovelmethod"]) == {"a", "b"}
    assert set(groups["title:adifferentmethod"]) == {"c"}


def test_dedup_groups_by_normalized_url() -> None:
    groups = group_candidates(
        [
            {"id": "a", "url": "https://example.org/paper#section-2"},
            {"id": "b", "url": "https://example.org/paper/"},
            {"id": "c", "url": "https://example.org/other"},
        ]
    )
    assert set(groups["url:https://example.org/paper"]) == {"a", "b"}
    assert set(groups["url:https://example.org/other"]) == {"c"}


def test_dedup_skips_records_without_identifiers() -> None:
    groups = group_candidates(
        [
            {"id": "a"},  # no doi / title / url -> skipped
            {"id": "b", "doi": "10.1/x"},
        ]
    )
    assert groups == {"doi:10.1/x": ["b"]}


def test_dedup_field_priority_doi_then_title_then_url() -> None:
    groups = group_candidates(
        [
            {"id": "a", "doi": "10.1/x", "title": "Whatever", "url": "https://e.org/x"},
            {"id": "b", "title": "Whatever", "url": "https://e.org/x"},
            {"id": "c", "url": "https://e.org/x"},
        ]
    )
    assert set(groups["doi:10.1/x"]) == {"a"}
    assert set(groups["title:whatever"]) == {"b"}
    assert set(groups["url:https://e.org/x"]) == {"c"}


def test_group_candidates_equivalent_to_reference_implementation() -> None:
    from tests.knowledge.test_literature_knowledge import (  # type: ignore[import-not-found]
        _normalize_title as ref_normalize_title,
        group_candidates as ref_group_candidates,
    )

    records = [
        {"id": "a", "doi": "10.1000/ABC"},
        {"id": "b", "doi": "10.1000/abc"},
        {"id": "c", "title": "A Novel Method"},
        {"id": "d", "title": "A  Novel  Method!"},
        {"id": "e", "url": "https://example.org/paper#sec"},
        {"id": "f", "url": "https://example.org/paper/"},
        {"id": "g"},
    ]
    assert group_candidates(records) == ref_group_candidates(records)
    for title in ("A Novel Method", "A  Novel  Method!", "Café Study", "Deep-Learning_Approaches."):
        assert normalize_title(title) == ref_normalize_title(title)


# ---------------------------------------------------------------------------
# conflict_flags (deduplication.md: mark only, never merge)
# ---------------------------------------------------------------------------


def _rec(**overrides: object) -> dict:
    base = {
        "id": "x",
        "doi": "10.1/x",
        "title": "Shared Title",
        "authors": ["Alice", "Bob"],
        "year": 2020,
        "venue_or_repository": "Venue",
    }
    base.update(overrides)
    return base


def test_conflict_flags_empty_for_single_record() -> None:
    assert conflict_flags([_rec()]) == []


def test_conflict_flags_empty_when_metadata_identical() -> None:
    a = _rec(id="a")
    b = _rec(id="b")
    assert conflict_flags([a, b]) == []


def test_conflict_authors_mismatch_on_order_difference() -> None:
    flags = conflict_flags([_rec(id="a"), _rec(id="b", authors=["Bob", "Alice"])])
    assert "authors_mismatch" in flags


def test_conflict_authors_mismatch_on_missing_authors() -> None:
    flags = conflict_flags([_rec(id="a"), _rec(id="b", authors=None)])
    assert "authors_mismatch" in flags


def test_conflict_year_mismatch() -> None:
    flags = conflict_flags([_rec(id="a"), _rec(id="b", year=2021)])
    assert "year_mismatch" in flags
    assert "authors_mismatch" not in flags
    assert "venue_mismatch" not in flags


def test_conflict_venue_mismatch() -> None:
    flags = conflict_flags([_rec(id="a"), _rec(id="b", venue_or_repository="Other Venue")])
    assert "venue_mismatch" in flags


def test_conflict_same_doi_diff_metadata() -> None:
    flags = conflict_flags(
        [
            _rec(id="a", doi="10.1000/ABC", title="Title One", authors=["A"], year=2020),
            _rec(id="b", doi="10.1000/abc", title="Title Two", authors=["B"], year=2021),
        ]
    )
    assert "same_doi_diff_metadata" in flags
    assert "authors_mismatch" in flags
    assert "year_mismatch" in flags


def test_conflict_flags_mark_only_never_merge() -> None:
    a = _rec(id="a", authors=["Alice"], year=2020, venue_or_repository="V1")
    b = _rec(id="b", authors=["Bob"], year=2021, venue_or_repository="V2")
    flags = conflict_flags([a, b])
    # Iron rule: only a list of flag strings comes back; no merged record, no
    # picked winner, no repaired metadata.
    assert isinstance(flags, list)
    assert flags and all(isinstance(flag, str) for flag in flags)
    assert a == _rec(id="a", authors=["Alice"], year=2020, venue_or_repository="V1")
    assert b == _rec(id="b", authors=["Bob"], year=2021, venue_or_repository="V2")


# ---------------------------------------------------------------------------
# CLI (`python -m cumcm_toolkit.literature.rules --group <json>`)
# ---------------------------------------------------------------------------


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "toolkit" / "src") + os.pathsep + str(REPO_ROOT)
    return env


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "-m", "cumcm_toolkit.literature.rules", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_env(),
    )


def _call_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["cumcm_toolkit.literature.rules", *argv])
    return cli_main()


def test_cli_group_success_returns_groups_and_conflicts() -> None:
    candidates = json.dumps(
        [
            {"id": "a", "doi": "10.1000/ABC", "title": "One", "authors": ["A"], "year": 2020, "venue_or_repository": "V"},
            {"id": "b", "doi": "10.1000/abc", "title": "Two", "authors": ["B"], "year": 2021, "venue_or_repository": "V"},
        ]
    )
    proc = _run_cli("--group", candidates)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload["groups"]["doi:10.1000/abc"]) == {"a", "b"}
    assert "same_doi_diff_metadata" in payload["conflicts"]["doi:10.1000/abc"]


def test_cli_group_conflict_free_groups_have_no_conflicts_entry() -> None:
    candidates = json.dumps(
        [
            {"id": "a", "doi": "10.1/x", "title": "T", "authors": ["A"], "year": 2020, "venue_or_repository": "V"},
            {"id": "b", "doi": "10.1/x", "title": "T", "authors": ["A"], "year": 2020, "venue_or_repository": "V"},
        ]
    )
    proc = _run_cli("--group", candidates)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload["groups"]["doi:10.1/x"]) == {"a", "b"}
    assert payload["conflicts"] == {}


def test_cli_group_bad_json_fails_closed() -> None:
    proc = _run_cli("--group", "{not json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"
    assert payload["error"]


def test_cli_group_not_an_array_fails_closed() -> None:
    proc = _run_cli("--group", '{"doi": "10.1/x"}')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_group_record_missing_id_fails_closed() -> None:
    proc = _run_cli("--group", '[{"doi": "10.1/x"}]')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failed"


def test_cli_missing_group_arg_usage_on_stderr_empty_stdout() -> None:
    # argparse-level failure: SystemExit(2), usage on stderr, EMPTY stdout
    # (the I-1 contract the TS bridge relies on).
    proc = _run_cli()
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr != ""


def test_cli_main_bad_json_direct_call(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = _call_main(monkeypatch, capsys, "--group", "{bad")
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error"]


def test_cli_main_success_direct_call(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    candidates = json.dumps(
        [
            {"id": "a", "title": "A Novel Method"},
            {"id": "b", "title": "A  Novel  Method!"},
        ]
    )
    code = _call_main(monkeypatch, capsys, "--group", candidates)
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["groups"]["title:anovelmethod"]) == {"a", "b"}
    assert payload["conflicts"] == {}
