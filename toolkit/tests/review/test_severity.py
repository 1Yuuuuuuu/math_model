from __future__ import annotations

import pytest

from cumcm_toolkit.review.severity import gate_status, is_blocking, validate_severity


@pytest.mark.parametrize("value", ["S0", "S1", "S2", "S3"])
def test_validate_severity_accepts_defined_levels(value: str) -> None:
    assert validate_severity(value) == value


@pytest.mark.parametrize("value", ["", "s1", "S4", "critical"])
def test_validate_severity_rejects_unknown_levels(value: str) -> None:
    with pytest.raises(ValueError, match="invalid severity"):
        validate_severity(value)


def test_only_open_s0_and_s1_block() -> None:
    assert is_blocking("S0")
    assert is_blocking("S1", "open")
    assert not is_blocking("S2")
    assert not is_blocking("S3")
    assert not is_blocking("S0", "resolved")
    assert is_blocking("S0", "accepted_risk")
    assert is_blocking("S1", "accepted_risk")
    assert not is_blocking("S2", "accepted_risk")


def test_gate_status_prioritizes_blocked_then_failed_then_passed() -> None:
    blocking = [{"severity": "S1", "status": "open"}]
    advisory = [{"severity": "S2", "status": "open"}]
    assert gate_status(blocking, ["missing capability"]) == "blocked"
    assert gate_status(blocking, []) == "failed"
    assert gate_status(advisory, []) == "passed"
