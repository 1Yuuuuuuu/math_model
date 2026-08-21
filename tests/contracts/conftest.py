import json
from pathlib import Path
import re
from datetime import datetime

import pytest
from jsonschema import FormatChecker


_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=ValueError)
def is_rfc3339_datetime_with_timezone(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_DATETIME.fullmatch(value):
        return False
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return True


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
