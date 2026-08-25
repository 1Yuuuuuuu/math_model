from __future__ import annotations

from pathlib import Path

import pytest

from cumcm_toolkit.workflow.config import load_workflow_config


ROOT = Path(__file__).resolve().parents[3]


def test_phase6_configs_define_exact_stages_gates_and_routes() -> None:
    config = load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )
    assert config["stage_order"] == [
        "intake",
        "model_design",
        "solve",
        "outline",
        "write",
        "review",
        "submission",
        "complete",
    ]
    assert list(config["gates"]) == [
        "gate_1_problem",
        "gate_2_model",
        "gate_3_outline",
        "gate_4_submission",
    ]
    assert config["literature_branch"]["skill"] == "literature-researcher"
    assert config["literature_branch"]["gate"] == "gate_3_outline"
    assert "gate_5" not in str(config)
    assert config["review"]["bundle_builder"] == "build_review_bundle"


def test_timeboxes_are_monotonic_and_end_at_72_hours() -> None:
    config = load_workflow_config(
        ROOT / "shared/workflows/stage-transitions.yaml",
        ROOT / "shared/workflows/cumcm-72h.yaml",
        skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
    )
    timeboxes = config["timeboxes"]
    assert timeboxes[0]["start_hour"] == 0
    assert timeboxes[-1]["end_hour"] == 72
    assert all(
        current["end_hour"] == following["start_hour"]
        for current, following in zip(timeboxes, timeboxes[1:])
    )


def test_duplicate_yaml_keys_and_unknown_skills_fail_closed(tmp_path: Path) -> None:
    transitions = tmp_path / "transitions.yaml"
    transitions.write_text("workflow_id: one\nworkflow_id: two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_workflow_config(
            transitions,
            ROOT / "shared/workflows/cumcm-72h.yaml",
            skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
        )

    schedule = (ROOT / "shared/workflows/cumcm-72h.yaml").read_text(encoding="utf-8")
    bad_schedule = tmp_path / "schedule.yaml"
    bad_schedule.write_text(
        schedule.replace("problem-reader", "unknown-dynamic-skill", 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown skill"):
        load_workflow_config(
            ROOT / "shared/workflows/stage-transitions.yaml",
            bad_schedule,
            skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
        )


def test_config_rejects_expression_or_import_keys(tmp_path: Path) -> None:
    schedule = tmp_path / "schedule.yaml"
    source = (ROOT / "shared/workflows/cumcm-72h.yaml").read_text(encoding="utf-8")
    schedule.write_text(source + "\npython_eval: dangerous\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_workflow_config(
            ROOT / "shared/workflows/stage-transitions.yaml",
            schedule,
            skill_catalog_path=ROOT / "adapters/codex/skills/catalog.json",
        )
