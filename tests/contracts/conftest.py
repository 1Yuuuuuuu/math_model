import json
from pathlib import Path
import re

import pytest
import rfc3339_validator
from jsonschema import FormatChecker


_LEAP_SECOND = re.compile(r"(?<=T\d{2}:\d{2}:)60(?=(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$)")


def _normalize_rfc3339_datetime(value: str) -> str:
    normalized = value
    if len(normalized) > 10 and normalized[10] == "t":
        normalized = f"{normalized[:10]}T{normalized[11:]}"
    if normalized.endswith("z"):
        normalized = f"{normalized[:-1]}Z"
    return _LEAP_SECOND.sub("59", normalized, count=1)


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def is_rfc3339_datetime(value: object) -> bool:
    return isinstance(value, str) and rfc3339_validator.validate_rfc3339(
        _normalize_rfc3339_datetime(value)
    )


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
