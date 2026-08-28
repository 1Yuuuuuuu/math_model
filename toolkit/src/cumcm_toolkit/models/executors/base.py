"""Validation primitives shared by all model executors."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from numbers import Integral, Real

import numpy as np


def json_finite_number(
    value: object, field: str, *, allow_none: bool = False
) -> float | None:
    """Normalize one plain-JSON number without invoking subclass conversions."""
    if value is None and allow_none:
        return None
    suffix = " or null" if allow_none else ""
    if type(value) not in (int, float):
        raise ValueError(f"{field}: must be a finite number{suffix}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must be a finite number{suffix}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}: must be a finite number{suffix}")
    return number


def required_field(payload: Mapping[str, object], field: str) -> object:
    """Return a required payload value, preserving a field-specific error."""
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field}: payload must be a mapping")
    try:
        return payload[field]
    except KeyError as exc:
        raise ValueError(f"{field}: field is required") from exc


def required_mapping(payload: Mapping[str, object], field: str) -> Mapping[str, object]:
    """Return a required object-valued payload field."""
    value = required_field(payload, field)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field}: must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field}: mapping keys must be strings")
    return value


def numeric_array(
    payload: Mapping[str, object],
    field: str,
    *,
    ndim: int | None = None,
    min_size: int = 1,
) -> np.ndarray:
    """Return a finite, non-boolean, non-complex numeric array from a payload."""
    value = required_field(payload, field)
    if isinstance(value, (str, bytes, bytearray, Mapping)):
        raise ValueError(f"{field}: must be a numeric array")
    if not isinstance(min_size, Integral) or isinstance(min_size, bool) or min_size < 1:
        raise ValueError(f"{field}: min_size must be a positive integer")
    if ndim is not None and (
        not isinstance(ndim, Integral) or isinstance(ndim, bool) or ndim < 0
    ):
        raise ValueError(f"{field}: ndim must be a non-negative integer or None")

    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: must be a rectangular numeric array") from exc

    if array.size == 0 or array.size < min_size:
        raise ValueError(f"{field}: must contain at least {min_size} value(s)")
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{field}: must have exactly {ndim} dimension(s)")
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.complexfloating)
    ):
        raise ValueError(f"{field}: must use a real numeric dtype")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{field}: must contain only finite values")
    return array


def finite_float(
    payload: Mapping[str, object],
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Return a finite real payload value, optionally constrained to a range."""
    value = required_field(payload, field)
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{field}: must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}: must be a finite number")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field}: must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field}: must be at most {maximum}")
    return number


def bounded_integer(
    payload: Mapping[str, object],
    field: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Return a non-boolean integer payload value, optionally constrained to a range."""
    value = required_field(payload, field)
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{field}: must be an integer")
    number = int(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{field}: must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field}: must be at most {maximum}")
    return number


def string_enum(
    payload: Mapping[str, object], field: str, choices: Collection[str]
) -> str:
    """Return a required string constrained to the supplied enumerated choices."""
    value = required_field(payload, field)
    if not isinstance(value, str):
        raise ValueError(f"{field}: must be a string")
    if value not in choices:
        raise ValueError(f"{field}: must be one of {', '.join(sorted(choices))}")
    return value


def reject_seed_random_state_conflict(
    payload: Mapping[str, object],
    *,
    seed_field: str = "seed",
    random_state_field: str = "random_state",
) -> None:
    """Reject simultaneous non-null seed and random-state declarations."""
    if not isinstance(payload, Mapping):
        raise ValueError("payload: must be a mapping")
    if payload.get(seed_field) is not None and payload.get(random_state_field) is not None:
        raise ValueError(f"conflict: both {seed_field} and {random_state_field} provided")
