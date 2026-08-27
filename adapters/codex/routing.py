from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cumcm_toolkit.models.specifications import get_spec


@dataclass(frozen=True)
class BackendCapability:
    available: bool
    approved: bool
    callable: bool

    @property
    def ready(self) -> bool:
        return self.available and self.approved and self.callable


def solver_execution_mode(model_id: str) -> str:
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    try:
        get_spec(model_id)
    except KeyError:
        return "plan-only"
    return "execute"


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_user_source_candidate(sources: Sequence[Mapping[str, object]]) -> bool:
    for source in sources:
        for key in ("doi", "url", "pdf_path"):
            if _non_empty_text(source.get(key)):
                return True
        author = source.get("author", source.get("authors"))
        has_author = _non_empty_text(author) or (
            isinstance(author, Sequence)
            and not isinstance(author, (str, bytes))
            and any(_non_empty_text(item) for item in author)
        )
        year = source.get("year")
        has_year = isinstance(year, int) and 1000 <= year <= 9999
        has_year = has_year or (_non_empty_text(year) and str(year).strip().isdigit())
        if _non_empty_text(source.get("title")) and has_author and has_year:
            return True
    return False


def route_literature_backend(
    *,
    runtime_search: BackendCapability,
    paper_skill: BackendCapability,
    user_sources: Sequence[Mapping[str, object]],
) -> str:
    """Select the highest-priority approved literature input without guessing."""
    if runtime_search.ready:
        return "runtime-search"
    if paper_skill.ready:
        return "paper-search-skill"
    if _has_user_source_candidate(user_sources):
        return "user-sources"
    raise RuntimeError("no approved literature backend is available")
