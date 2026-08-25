from pathlib import Path

from cumcm_toolkit.workflow.actions import next_action
from cumcm_toolkit.workflow.config import load_workflow_config


ROOT = Path(__file__).resolve().parents[2]


def _config() -> dict:
    return load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )


def _snapshot(branch: str, completed: list[str]) -> dict[str, object]:
    return {
        "state": {"stage": "solve"},
        "runtime_status": "running",
        "blocked_reason": None,
        "resume_when": [],
        "waiting_gate": None,
        "literature_branch": branch,
        "review_bundle_id": None,
        "completed_skills": completed,
    }


def test_literature_is_an_explicit_optional_branch_not_a_gate() -> None:
    config = _config()
    base = ["solver", "sensitivity-analyst"]
    assert next_action(_snapshot("undecided", base), config)["action_type"] == "decide_literature_branch"
    assert next_action(_snapshot("required", base), config)["skill"] == "literature-researcher"
    assert next_action(_snapshot("skipped", base), config)["action_type"] == "finalize_stage"
    assert config["literature_branch"]["gate"] == "gate_3_outline"
    assert "gate_5_literature" not in config["gates"]
