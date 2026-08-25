from pathlib import Path

from cumcm_toolkit.workflow.config import load_workflow_config


ROOT = Path(__file__).resolve().parents[2]


def test_four_human_gates_are_ordered_and_non_skippable() -> None:
    config = load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )
    assert config["gates"] == {
        "gate_1_problem": {"stage": "intake", "next_stage": "model_design"},
        "gate_2_model": {"stage": "model_design", "next_stage": "solve"},
        "gate_3_outline": {"stage": "outline", "next_stage": "write"},
        "gate_4_submission": {"stage": "review", "next_stage": "submission"},
    }
    assert list(config["gates"]) == [
        "gate_1_problem",
        "gate_2_model",
        "gate_3_outline",
        "gate_4_submission",
    ]
