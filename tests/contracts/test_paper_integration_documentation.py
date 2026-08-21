from pathlib import Path


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def markdown_section(document: str, heading: str) -> str:
    lines = document.splitlines()
    assert heading in lines, f"missing section: {heading}"
    start = lines.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        candidate = lines[index]
        candidate_level = len(candidate) - len(candidate.lstrip("#"))
        if candidate_level and candidate_level <= level and candidate[candidate_level :].startswith(" "):
            end = index
            break
    return "\n".join(lines[start:end])


def markdown_row(document: str, first_cell: str) -> list[str]:
    for line in document.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == first_cell:
            return cells
    raise AssertionError(f"missing table row: {first_cell}")


def verification_block(section: str) -> str:
    _, separator, remainder = section.partition("**Verification:**")
    assert separator, "missing verification subsection"
    _, separator, code = remainder.partition("```powershell")
    assert separator, "missing PowerShell verification block"
    return code.split("```", 1)[0]


def test_overall_design_routes_literature_as_an_optional_gate_3_input(
    project_root: Path,
) -> None:
    design = read(project_root, "docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md")
    workflow = markdown_section(design, "## 标准工作流与人工确认门")

    for route in (
        'D --> LD{"需要外部文献证据？"}',
        'LD -->|需要| L["受控检索候选文献"]',
        'LD -->|不需要| E["论文提纲与引用清单"]',
        'L --> E["论文提纲与引用清单"]',
    ):
        assert route in workflow
    assert "候选与拟支持主张随论文提纲在人工门 3 一并人工确认" in workflow
    assert "这不是第五个全局人工门" in workflow
    assert "人工门 5" not in workflow


def test_overall_design_scopes_legacy_entries_to_explicit_compatibility(
    project_root: Path,
) -> None:
    design = read(project_root, "docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md")
    compatibility = markdown_section(design, "### 兼容与 legacy 入口")

    assert "`cumcm-paper`" in compatibility
    assert "`math-modeling-paper`" in compatibility
    assert compatibility.count("用户显式选择") == 1
    assert "用户明确要求单 Skill 流程" in compatibility


def test_master_plan_makes_phase_1_depend_on_phase_0a(project_root: Path) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")
    phase_0a = markdown_row(plan, "Phase 0A 论文与文献整合底座")
    phase_1 = markdown_row(plan, "1 可复现底座")

    assert phase_0a[2] == "阶段 0"
    assert phase_1[2] == "Phase 0A"
    assert "`literature-source`、`citation-link`" in phase_0a[3]


def test_master_plan_verification_commands_cover_literature_owners(
    project_root: Path,
) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")
    expected_tests = {
        "## Phase 3: Codex modeling skills": "tests/e2e/test_literature_researcher_routing.py",
        "## Phase 6: Orchestrated competition flow": "tests/e2e/test_optional_literature_branch.py",
        "## Phase 7: DeepSeek Harness adapter": "tests/e2e/test_dsh_real_composition.py",
        "## Phase 8: Regression and controlled expansion": "tests/e2e/test_historical_citation_provenance.py",
    }

    for heading, expected_test in expected_tests.items():
        phase = markdown_section(plan, heading)
        assert expected_test in phase
        assert expected_test in verification_block(phase)


def test_capability_matrix_marks_planned_and_legacy_rows_explicitly(
    project_root: Path,
) -> None:
    matrix = read(project_root, "docs/architecture/paper-skill-capability-matrix.md")
    orchestrator = markdown_row(matrix, "`cumcm-orchestrator`")
    researcher = markdown_row(matrix, "`literature-researcher`")
    cumcm_legacy = markdown_row(matrix, "`cumcm-paper`")
    general_legacy = markdown_row(matrix, "`math-modeling-paper`")
    paper_search = markdown_row(matrix, "`paper-search`")

    assert orchestrator[4] == "规划中，未实现、未安装"
    assert researcher[4] == "规划中，未实现、未安装"
    assert "用户显式选择" in cumcm_legacy[1]
    assert "用户显式选择" in general_legacy[1]
    assert "CLI 当前不可用" in paper_search[4]
    assert "`cumcm_*` 工具在受检会话中不可用或未确认" in cumcm_legacy[4]


def test_paper_and_literature_guide_covers_routes_and_recovery(project_root: Path) -> None:
    guide = read(project_root, "docs/guides/paper-and-literature-workflow.md")
    for phrase in (
        "默认入口",
        "备选入口",
        "候选文献",
        "人工确认",
        "gate 3",
        "Codex",
        "DeepSeek Harness",
        "paper-search",
        "用户提供",
        "不得伪造",
        "当前不可用",
        "恢复",
    ):
        assert phrase in guide
