from __future__ import annotations

import pytest

from adapters.codex.routing import BackendCapability, route_literature_backend


def test_prefers_runtime_search_then_paper_skill_then_user_sources() -> None:
    ready = BackendCapability(available=True, approved=True, callable=True)
    absent = BackendCapability(available=False, approved=False, callable=False)
    sources = [{"doi": "10.1000/example"}]
    assert route_literature_backend(runtime_search=ready, paper_skill=ready, user_sources=sources) == "runtime-search"
    assert route_literature_backend(runtime_search=absent, paper_skill=ready, user_sources=sources) == "paper-search-skill"
    assert route_literature_backend(runtime_search=absent, paper_skill=absent, user_sources=sources) == "user-sources"


@pytest.mark.parametrize(
    "capability",
    [
        BackendCapability(available=True, approved=False, callable=True),
        BackendCapability(available=True, approved=True, callable=False),
        BackendCapability(available=False, approved=True, callable=True),
    ],
)
def test_unapproved_unavailable_or_uncallable_backend_is_not_selected(
    capability: BackendCapability,
) -> None:
    unavailable = BackendCapability(False, False, False)
    with pytest.raises(RuntimeError, match="no approved literature backend"):
        route_literature_backend(
            runtime_search=capability,
            paper_skill=unavailable,
            user_sources=[],
        )


def test_no_backend_fails_closed() -> None:
    unavailable = BackendCapability(False, False, False)
    with pytest.raises(RuntimeError, match="no approved literature backend"):
        route_literature_backend(
            runtime_search=unavailable,
            paper_skill=unavailable,
            user_sources=[{"title": "metadata without a stable locator"}],
        )


def test_user_metadata_candidate_is_accepted_without_doi_url_or_pdf() -> None:
    unavailable = BackendCapability(False, False, False)
    assert route_literature_backend(
        runtime_search=unavailable,
        paper_skill=unavailable,
        user_sources=[
            {
                "title": "A user supplied method note",
                "author": "Example Author",
                "year": 2024,
            }
        ],
    ) == "user-sources"
