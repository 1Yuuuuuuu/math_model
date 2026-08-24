from __future__ import annotations

import math
from typing import Any

import numpy as np


def is_finite_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def ensure_finite(value: Any, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric value in {where}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite number in {where}: {value}")
    return number


def to_python_scalar(value: Any) -> object:
    if hasattr(value, "item"):
        return value.item()
    return value
