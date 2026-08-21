from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.contract_formats import FORMAT_CHECKER
from scripts.validate_contracts import load_json


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT
