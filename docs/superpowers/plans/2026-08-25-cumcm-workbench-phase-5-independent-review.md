# Phase 5 Independent Review Foundation Implementation Plan

> **状态：历史基础计划已完成。** Phase 4 合流、五个 Reviewer Skill、评分卡和 Phase 6 汇总由 `2026-08-25-cumcm-workbench-phase-5-completion.md` 接续并完成。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付不依赖 Phase 4 最终论文/PDF 的五套评审量表、只读评审引擎、审批失效机制和 Codex `model-reviewer` Skill。

**Architecture:** `shared/rubrics/` 是版本化评审规则唯一来源；`cumcm_toolkit.review` 只执行注册检查器并生成不可变输入哈希报告；`model-reviewer` 消费 Phase 3 交接物并调用模型/复现门。依赖 Phase 4 的门在缺少能力时显式 `blocked`。

**Tech Stack:** Python 3.11、pytest、PyYAML、jsonschema Draft 2020-12、Agent Skills、SHA-256、RFC 3339。

**Spec:** `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-5-independent-review-design.md`

## Global Constraints

- 不修改 DSH 正在实施的 Phase 4 文件、接口或依赖锁。
- 评审过程只读，不接受修订回调，不改写任何被审文件。
- S0/S1 open finding 阻断；S2/S3 只记录。
- 缺证据索引或必需能力返回 `blocked`，不得返回 `passed`。
- finding 必须符合 `shared/contracts/review-finding.schema.json`；无现存 `clm_*` 时不得伪造。
- YAML 检查器必须来自固定注册表，禁止表达式、代码和任意导入路径。
- 规范 JSON 拒绝 NaN/Infinity；哈希为 64 位小写 SHA-256。
- `paper-reviewer`、Phase 4 报告映射和最终投稿聚合明确延后。

---

### Task 1: 五套版本化评审量表

**Files:**

- Create: `shared/rubrics/reproducibility.yaml`
- Create: `shared/rubrics/model-quality.yaml`
- Create: `shared/rubrics/paper-quality.yaml`
- Create: `shared/rubrics/red-team.yaml`
- Create: `shared/rubrics/submission.yaml`
- Create: `toolkit/tests/review/test_rubrics.py`

**Interfaces:**

- 每个文件输出 `{rubric_id, version, review_gate, requires_capabilities, rules}`。
- 每条 rule 输出 `{rule_id, severity, checker, params, summary, evidence_paths, recommendation}`。
- `review_gate` 取 `hard|reproducibility|model|paper|red_team`；submission 使用 `hard`。
- 合法 checker 为 `required_path|non_empty|equals|all_present|hash_matches`。

- [ ] 写失败测试：遍历五个预期路径，断言唯一 rubric/rule ID、version `"1.0"`、合法 gate/severity/checker、非空 summary/recommendation，且 Phase 4 相关量表声明 capability。
- [ ] 运行 `python -m pytest toolkit/tests/review/test_rubrics.py -v -p no:cacheprovider`，确认因目录缺失失败。
- [ ] 创建五个最小量表；复现/模型规则覆盖输入完整、基线、验证、实验身份和敏感性，论文/红队/投稿规则声明所需 Phase 4 能力。
- [ ] 重跑定向测试至通过。

### Task 2: 严重度裁决

**Files:**

- Create: `toolkit/src/cumcm_toolkit/review/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/review/severity.py`
- Create: `toolkit/tests/review/test_severity.py`

**Interfaces:**

- `validate_severity(value: str) -> str`：仅接受 `S0|S1|S2|S3`。
- `is_blocking(severity: str, status: str = "open") -> bool`：open S0/S1 为真；resolved/accepted_risk 或 S2/S3 为假。
- `gate_status(findings: list[dict], errors: list[str]) -> str`：errors 非空为 `blocked`，否则有阻断 finding 为 `failed`，其余 `passed`。

- [ ] 写失败测试：覆盖四级严重度、非法值、open/resolved/accepted_risk 和三种门状态。
- [ ] 运行测试并确认模块缺失。
- [ ] 实现最小纯函数并重跑至通过。

### Task 3: 只读评审引擎

**Files:**

- Create: `toolkit/src/cumcm_toolkit/review/engine.py`
- Create: `toolkit/tests/review/test_engine.py`

**Interfaces:**

- `canonical_digest(value: object) -> str`：排序键、紧凑 UTF-8 JSON、`allow_nan=False` 后 SHA-256。
- `load_rubric(path: Path) -> dict[str, object]`：安全读取 YAML 并验证固定字段、ID 唯一性和 checker 注册表。
- `review(inputs: dict, rubric: dict, *, capabilities: set[str] | None = None, reviewed_at: str | None = None) -> dict`：预检 evidence_refs/capability；运行规则；用现存 evidence_refs 生成契约有效 finding；返回 report。
- `is_review_current(report: dict, inputs: dict) -> bool`：比较 `input_digest`。
- 检查器支持点路径：`required_path(path)`、`non_empty(path)`、`equals(path, expected)`、`all_present(paths)`、`hash_matches(path, expected_path)`。

- [ ] 写失败测试：规范哈希确定性/NaN 拒绝、量表非法 checker 拒绝、合法输入 passed、S1 失败、缺 evidence blocked、缺 capability blocked、finding 通过 Schema、修改输入失效。
- [ ] 运行测试并确认导入失败。
- [ ] 实现检查器注册表、点路径读取、finding 生成和报告哈希。
- [ ] 重跑引擎、严重度、量表测试至通过。

### Task 4: 隔离、只读与强制复审 E2E

**Files:**

- Create: `tests/e2e/test_review_isolation.py`
- Create: `tests/e2e/test_revision_requires_rereview.py`

**Interfaces:**

- 模型门只返回 `model-quality` 规则的 finding ID；不得出现 paper/red-team 规则。
- 评审临时 Phase 3 产物目录前后计算文件 SHA-256，结果必须相等。
- 原输入 `is_review_current=True`；修改任一被审字段后为 false；重新评审产生新的 review ID。

- [ ] 写两个失败 E2E，使用合成 Phase 3 handoff 和 `clm_model_review`。
- [ ] 运行测试，确认因引擎行为未完成或量表缺失失败。
- [ ] 只修复评审内核中的最小缺口，不向引擎添加写文件能力。
- [ ] 重跑两个 E2E 至通过。

### Task 5: Codex model-reviewer Skill

**Files:**

- Create: `adapters/codex/skills/model-reviewer/SKILL.md`
- Create: `adapters/codex/skills/model-reviewer/agents/openai.yaml`
- Create: `adapters/codex/skills/model-reviewer/resources.json`
- Modify: `scripts/package_codex_skills.py`
- Modify: `tests/snapshots/codex-skills/routing-cases.yaml`
- Modify: `tests/snapshots/codex-skills/test_skill_contracts.py`
- Modify: `tests/snapshots/codex-skills/test_packaging.py`

**Interfaces:**

- Skill 输入：五类 Phase 3 handoff + `clm_*` evidence_refs；输出只读 review report。
- Skill 不修改模型、参数、代码或实验；缺任一必需 handoff/evidence 返回 blocked。
- 打包器预期 Skill 数从 6 扩展到 7，`model-reviewer` 自包含打包 rubrics、review engine/severity、review-finding schema。

- [ ] 先扩展路由/契约/打包测试，运行并确认因 `model-reviewer` 缺失而失败。
- [ ] 按仓库既有 Skill 目录约定创建 Skill 文件、UI 元数据和资源声明，不把仓库外的初始化脚本写成项目依赖。
- [ ] 更新发行 catalog，运行 Phase 3/5 Skill 契约与自包含打包测试至通过；当前运行时若公开额外 Skill 校验器，可作为附加检查。

### Task 6: 验收与交接

**Files:**

- Create: `docs/operations/review-gates.md`
- Modify: `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-5-independent-review-design.md`（状态改为已实施）

**Interfaces:**

- 使用文档解释五门、S0-S3、blocked/failed/passed、旧审批失效和 Phase 4 合流边界。

- [ ] 运行 `python -m pytest toolkit/tests/review tests/e2e/test_review_isolation.py tests/e2e/test_revision_requires_rereview.py tests/snapshots/codex-skills -v -p no:cacheprovider`。
- [ ] 运行 `python scripts/package_codex_skills.py --check` 和六个 Phase 3 Skill 加 Phase 5 `model-reviewer` 的仓库级校验。
- [ ] 运行完整 pytest、契约验证器、`git diff --check` 和状态检查。
- [ ] 确认 Phase 4 未跟踪/在建文件未被修改，记录延后项和 DSH 合流能力名。
