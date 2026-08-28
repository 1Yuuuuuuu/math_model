from __future__ import annotations

import pytest

from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.executors.base import finite_float


HUGE_JSON_INTEGER = 10**1000


def test_finite_float_translates_integer_conversion_overflow() -> None:
    """Removing OverflowError conversion would expose Python's float implementation."""
    with pytest.raises(ValueError, match=r"rho: must be a finite number"):
        finite_float({"rho": HUGE_JSON_INTEGER}, "rho")


@pytest.mark.parametrize(
    ("model_id", "payload", "field"),
    [
        (
            "grey-relational-analysis",
            {
                "reference": [1, 2],
                "comparatives": [[1, 2]],
                "rho": HUGE_JSON_INTEGER,
            },
            "rho",
        ),
        (
            "anomaly-detection",
            {
                "matrix": [[1], [2], [10]],
                "method": "iqr",
                "multiplier": HUGE_JSON_INTEGER,
            },
            "multiplier",
        ),
        (
            "anomaly-detection",
            {
                "matrix": [[1], [2], [10]],
                "method": "zscore",
                "threshold": HUGE_JSON_INTEGER,
            },
            "threshold",
        ),
        (
            "anomaly-detection",
            {
                "matrix": [[1], [2], [10]],
                "method": "isolation-forest",
                "contamination": HUGE_JSON_INTEGER,
            },
            "contamination",
        ),
    ],
)
def test_public_finite_float_consumers_translate_integer_conversion_overflow(
    model_id: str, payload: dict[str, object], field: str
) -> None:
    """Shared finite-number consumers must expose model/stage context, never overflow."""
    with pytest.raises(
        ValueError,
        match=rf"{model_id}: execution stage failed: {field}: must be a finite number",
    ):
        execute(model_id, payload)
