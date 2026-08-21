from pathlib import Path


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def test_overall_design_defines_controlled_literature_route(project_root: Path) -> None:
    design = read(project_root, "docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md")
    for phrase in (
        "literature-researcher",
        "候选文献",
        "人工确认",
        "不得伪造",
        "cumcm-paper",
        "math-modeling-paper",
    ):
        assert phrase in design


def test_master_plan_contains_phase_0a_and_stage_owners(project_root: Path) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")
    for phrase in (
        "Phase 0A",
        "literature-source",
        "citation-link",
        "Phase 3",
        "Phase 4",
        "Phase 6",
        "Phase 7",
        "Phase 8",
    ):
        assert phrase in plan


def test_capability_matrix_keeps_legacy_skills_as_explicit_options(project_root: Path) -> None:
    matrix = read(project_root, "docs/architecture/paper-skill-capability-matrix.md")
    for phrase in (
        "cumcm-orchestrator",
        "literature-researcher",
        "cumcm-paper",
        "math-modeling-paper",
        "paper-search",
        "当前不可用",
        "用户显式选择",
        "不直接复制",
        "三个个人 Skill 文件夹均存在",
        "cumcm_*",
        "不可用或未确认",
    ):
        assert phrase in matrix
