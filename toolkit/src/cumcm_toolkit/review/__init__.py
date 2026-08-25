"""Deterministic, read-only review gates."""

from cumcm_toolkit.review.bundle import REVIEW_SLOTS, build_review_bundle
from cumcm_toolkit.review.engine import is_review_current, load_rubric, review
from cumcm_toolkit.review.inputs import (
    build_paper_inputs,
    build_reproducibility_inputs,
    build_submission_inputs,
)
from cumcm_toolkit.review.scorecard import evaluate_scorecard

__all__ = [
    "REVIEW_SLOTS",
    "build_paper_inputs",
    "build_reproducibility_inputs",
    "build_review_bundle",
    "build_submission_inputs",
    "evaluate_scorecard",
    "is_review_current",
    "load_rubric",
    "review",
]
