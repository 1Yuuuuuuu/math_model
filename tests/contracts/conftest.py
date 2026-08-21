import json
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.contract_formats import FORMAT_CHECKER


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
