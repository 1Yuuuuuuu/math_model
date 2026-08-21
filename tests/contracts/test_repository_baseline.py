from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_required_project_metadata_exists() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.12"' in pyproject
    ignores = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".venv/", ".superpowers/", "dist/", "workspaces/", "__pycache__/"):
        assert entry in ignores
