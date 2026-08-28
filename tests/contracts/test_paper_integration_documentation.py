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


def test_master_plan_marks_phase_7_complete_and_phase_8_next(
    project_root: Path,
) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")

    assert "- [x] Phase 0A：" in plan
    assert "- [x] 阶段 1：" in plan
    assert "- [x] 阶段 2：" in plan
    assert "- [x] 阶段 3：" in plan
    assert "- [x] 阶段 4：" in plan
    assert "- [x] 阶段 5：" in plan
    assert "- [x] 阶段 6：" in plan
    assert "- [x] 阶段 7：" in plan
    assert "下一步是阶段 8 的真题回归" in plan
    assert "下一步是阶段 7 的 DSH 适配" not in plan
    assert "下一步是阶段 6 的构思与详细设计" not in plan
    assert "当前执行入口是 Phase 0A" not in plan


def test_phase5_operations_document_complete_review_handoff(project_root: Path) -> None:
    guide = read(project_root, "docs/operations/review-gates.md")
    handoff = read(project_root, "docs/operations/phase5-to-phase6-handoff.md")
    combined = guide + handoff
    for phrase in (
        "submission-auditor",
        "repro-reviewer",
        "model-reviewer",
        "paper-reviewer",
        "red-team-reviewer",
        "85",
        "70",
        "ready_for_phase_6",
        "15",
        "12",
        "生成与评审隔离",
    ):
        assert phrase in combined
    assert "shared/contracts/review-bundle.schema.json" in handoff
    assert "build_review_bundle" in handoff
    assert "真实 Agent 前向观测" in handoff


def test_historical_phase_0_plan_preserves_nine_contract_scope_and_phase_0a_handoff(
    project_root: Path,
) -> None:
    phase_0 = read(
        project_root,
        "docs/superpowers/plans/2026-08-21-cumcm-workbench-phase-0-contracts.md",
    )
    task_8 = markdown_section(phase_0, "### Task 8: Fresh-clone verification and phase handoff")
    completion = markdown_section(phase_0, "## Phase 0 completion criteria")

    assert 'assert payload["contracts"] == 9' in phase_0
    assert '"contracts": 9' in phase_0
    assert "all nine contracts" in phase_0
    assert "reports nine contracts" in completion
    assert "eleven contracts" not in phase_0
    assert '"contracts": 11' not in phase_0
    assert "Phase 0A" in task_8
    assert "Phase 1 planning may begin" not in task_8
    assert "authorizes creation of the Phase 0A detailed plan" in completion
    assert "authorizes creation of the Phase 1 detailed plan" not in completion


def test_phase_2_owns_literature_knowledge_without_runtime_skill(project_root: Path) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")
    phase_2 = markdown_section(plan, "## Phase 2: High-frequency model core")
    phase_3 = markdown_section(plan, "## Phase 3: Codex modeling skills")

    for deliverable in (
        "shared/knowledge/literature/search-strategy.md",
        "shared/knowledge/literature/deduplication.md",
        "shared/knowledge/literature/source-evaluation.md",
        "tests/knowledge/test_literature_knowledge.py",
    ):
        assert deliverable in phase_2
    assert "tests/knowledge/test_literature_knowledge.py" in verification_block(phase_2)
    for rule in ("DOI、规范化标题和来源标识", "引用量或期刊等级", "元数据冲突"):
        assert rule in phase_2
    assert "不实现运行时 Skill" in phase_2
    assert "adapters/codex/skills/literature-researcher/" not in phase_2
    assert "adapters/codex/skills/literature-researcher/" in phase_3

    matrix = read(project_root, "docs/architecture/paper-skill-capability-matrix.md")
    ownership = markdown_section(matrix, "## 后续阶段所有权")
    assert "Phase 2" in ownership
    assert "检索知识、去重规则和来源评价规则" in ownership
    assert "Phase 3" in ownership
    assert "运行时" in ownership


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
        "人工门 3“确认论文提纲”",
        "Codex",
        "DeepSeek Harness",
        "paper-search",
        "用户提供",
        "不得伪造",
        "当前不可用",
        "恢复",
    ):
        assert phrase in guide


def test_guide_distinguishes_outline_approval_from_quality_gate_3(project_root: Path) -> None:
    guide = read(project_root, "docs/guides/paper-and-literature-workflow.md")
    future = markdown_section(guide, "## 为未来分阶段工作流做准备")

    assert "四个全局人工确认门中的第三个" in future
    assert "人工门 3“确认论文提纲”" in future
    assert "`Gate 3 论文审查`" in future
    assert "不能替代" in future
    assert "gate 3` 指论文审查质量门" not in future


def test_guide_says_contracts_exist_but_runtime_producers_are_planned(
    project_root: Path,
) -> None:
    guide = read(project_root, "docs/guides/paper-and-literature-workflow.md")
    codex = markdown_section(guide, "### 在 Codex 中操作")

    assert "`literature-source` 与 `citation-link` 契约已经登记" in codex
    assert "运行时生产者与消费者仍在规划中" in codex
    assert "未来的 `literature-source` 与 `citation-link` 契约" not in codex


def test_contract_docs_define_future_literature_cross_record_invariants(
    project_root: Path,
) -> None:
    contracts = read(project_root, "docs/architecture/contracts.md")
    section = markdown_section(contracts, "## 文献契约的跨记录边界")

    for invariant in (
        "gate_3_outline",
        "verification_status = approved",
        "主检索内容",
        "逐 artifact",
        "修订后旧链接失效",
    ):
        assert invariant in section
    assert "当前单记录 JSON Schema 不声称执行这些跨记录检查" in section
