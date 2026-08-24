# Phase 4 论文生产线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付只使用固化结果、实验与引用证据链的论文生产线确定性核心：CUMCM LaTeX 模板、写作知识、latex/evidence/pdf 八个 toolkit 模块与端到端论文管线测试。

**Architecture:** 论文生产线分两条轨道：① 确定性工具核心（本计划）——`toolkit/src/cumcm_toolkit/{latex,pdf,evidence}/` 八模块 + `shared/templates/latex/cumcm/` 模板 + `shared/knowledge/writing/` 知识，全部复用 Phase 0/0A/1/2 已验证契约（evidence-link、citation-link、literature-source、experiment、artifact 与 results/export 输出）；② Codex Skill 轨道（`adapters/codex/skills/paper-{outliner,writer,latex-publisher}/`）由 Codex 轨道承担（与 Phase 3 分工一致），消费本计划的稳定接口。端到端测试 `tests/e2e/test_paper_pipeline.py` 用 toolkit 直接验证"证据绑定 → 编译 → 引用校验 → PDF 检查"闭环。

**Tech Stack:** Windows、Python 3.11、uv、pytest、XeLaTeX/ctex（MiKTeX）、latexmk（可选，本机缺 Perl 用 xelatex 双遍）、pypdf（新增依赖，用于 PDF 字体/空白页检查）、JSON Schema Draft 2020-12、`jsonschema`、`referencing`。

**Spec:** `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（Phase 4 章节，第 283–319 行）与 `docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`（工具体系、证据链、论文与 LaTeX 文档类别）。

## Global Constraints

- 论文数值必须来自真实数据与真实运行结果（实验记录、结果导出文件）；任何数值必须能解析到证据 ID；不得补写、猜测或伪造。
- 引用只能来自已批准的 `literature-source`（`verification_status = approved` + 人工 `decision_id`）；`citation-check` 必须校验正文 `\cite`、参考文献条目、定位与 `citation-link` 一一对应。
- 失败显式化（fail-closed）：编译失败、未定义引用、缺失图片、证据缺失、来源未批准 → 结构化失败，不静默降级。
- 主生产线 XeLaTeX + PDF；Windows 不依赖符号链接；时间 RFC 3339 带时区；路径可移植；JSON 严格（拒绝 NaN/Infinity）。
- `shared/` 唯一事实来源；toolkit 只读消费。
- 新增依赖只允许：pypdf（`pdf/inspect` 用）。
- 每个任务独立提交并通过新鲜评审；先 RED 后 GREEN；变更面驱动验证，Task 10 里程碑完整回归。
- 本计划不实现 `adapters/codex/skills/paper-*`（Codex 轨道）；不实现 DSH 插件（Phase 7）。
- 沙盒事实（沿用 Phase 1-2）：升级命令忽略 workdir（用 `git -C`/Set-Location）、测试用 worktree `.venv` 绝对路径 + `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider`、git 提交由用户执行、评审者用只读 git 自取 diff。

## 已探测的环境事实（2026-08-22，Phase 4 计划输入）

| 项 | 探测结果 |
| --- | --- |
| 仓库状态 | `main` = `e3bb79d`（Phase 0/0A/1/2 全部合入并推送 origin） |
| Phase 1-2 交付 | 四+八 toolkit 模块；11 契约（含 evidence-link、literature-source、citation-link）；results/export（严格 JSON）；最小 latex 模板与 xelatex 双遍构建测试 |
| Python/依赖 | 3.11.9；numpy/pandas/scipy/sklearn/statsmodels/matplotlib/PyYAML 已锁定；pypdf 需新增 |
| TeX | MiKTeX 用户级；xelatex 可用；latexmk 缺 Perl 不可用 → 本阶段构建用 xelatex 双遍；ctex 模板首次编译可能需装包（升级权限运行时可自动安装） |
| 契约字段（证据绑定依据） | evidence-link：`claim_id`(clm_)/`claim_text`/`artifact_id`(art_)/`experiment_id`(exp_)/`locator{kind,value}`/`boundary`；citation-link：`citation_id`(cite_)/`claim_id`(clm_)/`source_id`(src_)/`usage`/`locator`/`support_boundary`/`verified_at`；literature-source：`verification_status`/`decision_id`/`canonical_url`/`content_sha256` |

## 本计划的设计决策（Ruling，执行时据此判定）

1. **证据绑定语义**：`evidence/linker.py` 生成符合 Phase 0 `evidence-link.schema.json` 的记录（claim → artifact/experiment + 定位 + 支持边界）；"摘要每个关键数值可解析到证据 ID"由 e2e 测试落地：摘要中的数字必须出现在其链接记录的 metrics 或 locator 中，否则检查失败。
2. **引用绑定语义**：`evidence/citation_linker.py` 只接受 `verification_status = approved` 的 `literature-source`（含 decision_id），生成符合 Phase 0A `citation-link.schema.json` 的记录；未批准来源抛 `ValueError`（人工门 3 的 toolkit 侧表达）。
3. **BibTeX 生成**：`latex/bibliography.py` 从 approved 来源生成确定性 BibTeX（key 由 `source_id` 派生，字段映射 DOI/标题/作者/年份/venue，URL 保留，不编造字段）。
4. **引用校验**：`latex/citation_check.py` 校验：正文 `\cite{key}` 集合 ⊆ BibTeX 条目集合；每个 BibTeX 条目对应一个 approved 来源；每个引用对应一条 citation-link（claim/usage/locator/support_boundary 齐备）；输出结构化报告 `{status, missing_bibtex, unapproved_sources, uncited_entries, unmatched_citations, errors}`。
5. **构建与 PDF 检查**：`latex/build.py` 用 xelatex 双遍（沿用 Phase 1 日志解析：页数、undefined 引用、错误行），`latex/lint.py` 检查标签/符号/未引用图表/占位标记；`pdf/inspect.py` 用 **pypdf** 读取页数、字体（embedding 状态）、逐页文本判空白页，输出结构化报告。
6. **CUMCM 模板**：`shared/templates/latex/cumcm/` 用 `ctexart`（真中文排版），含摘要/关键词/章节骨架/`\label`/`\ref`/`\cite` 占位与"证据绑定说明"注释；minimal 模板（Phase 1）保留不动。
7. **写作知识**：`shared/knowledge/writing/*.md` 按 Phase 1 基础文档的结构检查模式（五小节），主题：结构、摘要、图表、公式符号、引用原创性、编译排错。
8. **e2e 管线**：`tests/e2e/test_paper_pipeline.py`：造实验记录 + 结果导出 + approved 来源 → scaffold 论文工程 → 写入证据绑定正文（数字来自实验 metrics、引用来自 approved 来源）→ build（xelatex 双遍）→ citation_check → pdf_inspect → 断言各环节结构化报告与退出标准。
9. **新增 pypdf** 依赖（仅 pdf/inspect；纯 Python，可锁定）。

## File structure and ownership

| 文件 | 单一职责 |
| --- | --- |
| `pyproject.toml` | 追加 `pypdf>=4,<7` 依赖 |
| `shared/templates/latex/cumcm/{main.tex,cumcm.sty,bibliography.bib(空)}` | CUMCM 论文模板（ctexart） |
| `shared/knowledge/writing/{structure,abstract,figures-tables,formulas-symbols,citation-originality,latex-debug}.md` | 6 篇写作知识文档（五小节） |
| `toolkit/src/cumcm_toolkit/latex/{__init__,scaffold,build,lint,bibliography,citation_check}.py` | 论文工程/构建/静态检查/BibTeX/引用校验 |
| `toolkit/src/cumcm_toolkit/pdf/{__init__,inspect}.py` | PDF 结构化检查 |
| `toolkit/src/cumcm_toolkit/evidence/{__init__,linker,citation_linker}.py` | 证据链接与引用链接 |
| `toolkit/tests/{latex,pdf,evidence}/test_*.py` | 各模块单元测试 |
| `tests/knowledge/test_writing_structure.py` | 写作知识结构检查（复用五小节模式） |
| `tests/e2e/test_paper_pipeline.py` | 端到端证据绑定论文管线 |
| `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md` | Task 10 更新（含与 Codex 轨道分工说明） |

## Execution preflight: 分支与依赖

1. worktree 分支（如 `.worktrees/phase-4-paper-pipeline -b phase-4-paper-pipeline`）。
2. `pyproject.toml` dependencies 追加 `"pypdf>=4,<7"`；`uv lock` + `uv sync --dev`（用主树 bootstrap-uv，Set-Location 到 worktree；worktree `.venv` 建好全部依赖）。

---

### Task 1: CUMCM 论文模板与写作知识

**Files:**

- Create: `shared/templates/latex/cumcm/main.tex`
- Create: `shared/templates/latex/cumcm/cumcm.sty`
- Create: `shared/templates/latex/cumcm/bibliography.bib`（空占位，含注释说明）
- Create: `shared/knowledge/writing/structure.md`（论文结构）
- Create: `shared/knowledge/writing/abstract.md`（摘要）
- Create: `shared/knowledge/writing/figures-tables.md`（图表）
- Create: `shared/knowledge/writing/formulas-symbols.md`（公式与符号）
- Create: `shared/knowledge/writing/citation-originality.md`（引用与原创性）
- Create: `shared/knowledge/writing/latex-debug.md`（编译排错）
- Create: `tests/knowledge/test_writing_structure.py`

**Interfaces:**

- 模板 `main.tex`：`ctexart` 文档类，含标题/摘要/关键词/正文章节骨架（引言、问题重述、模型假设、符号说明、模型建立与求解、模型检验、敏感性分析、模型评价与推广、参考文献）；`\label` 示例、`\ref` 前向引用、`\cite{key}` 占位注释；文件头注释声明"正文数值必须来自证据链，引用必须来自已批准来源"。
- `cumcm.sty`：包依赖（ctex、booktabs、graphicx、amsmath、hyperref 等）与页边距/标题样式。
- `bibliography.bib`：空文件 + `% 由 bibliography 工具从已批准 literature-source 生成` 注释。
- 6 篇写作知识文档：每篇必备小节 `## 是什么`、`## 为什么重要`、`## 常见误区`、`## 在本工作台中的用法`、`## 一句话总结`（与 Phase 1 基础文档同模式）；`citation-originality.md` 必须明确"候选文献≠引用、未经批准不得引用、引用量≠质量"。
- `test_writing_structure.py`：遍历 6 篇文档断言五小节 + 长度 + 无标记；断言模板文件存在且 `main.tex` 含 `ctexart`、`\cite`、证据声明注释。

- [ ] **Step 1: 写失败测试**（tests/knowledge/test_writing_structure.py，五小节检查复用 Phase 1 模式 + 模板断言）
- [ ] **Step 2: RED**（文档/模板缺失）
- [ ] **Step 3: 创建模板与 6 篇文档**（中文；模板可编译性由 Task 3 的 build 测试验证，本任务只保证文件与结构）
- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add cumcm latex template and writing knowledge`）

### Task 2: 论文工程 scaffold

**Files:**

- Create: `toolkit/src/cumcm_toolkit/latex/scaffold.py`
- Create: `toolkit/tests/latex/test_scaffold.py`

**Interfaces:**

- `scaffold_paper(target_root: Path, paper_id: str, *, template_root: Path | None = None, overwrite: bool = False) -> dict[str, object]`：从 `shared/templates/latex/cumcm/` 复制论文工程（复制 `main.tex`、`cumcm.sty`、`bibliography.bib` 到 `target_root/paper_id/`）；默认不覆盖已有文件（FileExistsError）；模板缺失抛 FileNotFoundError；`paper_id` 校验（单段可移植，复用 `is_cumcm_workspace_path` + 禁 `/`、`\`）；返回 `{paper_id, root, files:[{path, size, sha256}]}`（与 Phase 1 scaffold 同模式）。

- [ ] **Step 1: 失败测试**（创建/拒绝覆盖/非法 id/模板缺失/CLI 失败 JSON——复用 Phase 1 scaffold 测试模式；CLI 子进程测试需 env PYTHONPATH 双路径，沿用既有裁决）
- [ ] **Step 2: RED** → **Step 3: 实现**（复用 Phase 1 scaffold 的 `parents[4]` 与路径规则）→ **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add paper project scaffold`）

### Task 3: LaTeX 构建 build

**Files:**

- Create: `toolkit/src/cumcm_toolkit/latex/build.py`
- Create: `toolkit/tests/latex/test_build.py`

**Interfaces:**

- `build_paper(work_dir: Path, *, passes: int = 2, timeout: float = 600.0) -> dict[str, object]`：在 work_dir 内用 xelatex 跑 `passes` 遍（`-interaction=nonstopmode -halt-on-error`）；返回 `{status: "ok"|"failed", passes, errors:[...], warnings:[...], pages: int|None, undefined_references:[...], pdf_path, log_path}`；解析 `main.log`：`Output written on main.pdf (N page` 取页数、`Reference ... undefined on input line` 取未定义引用、`! ` 错误行、`LaTeX Warning:` 警告；任一 pass 失败 → `status="failed"`（不静默降级）；`xelatex` 缺失 → `ValueError`。
- 复用 Phase 1 的日志解析经验；`pdf_path = work_dir/"main.pdf"`。

- [ ] **Step 1: 失败测试**（tmp 内放最小 ctex 文档：正常编译 → ok + pages ≥ 1 + 无 undefined；含前向引用 → 双遍后无 undefined；故意错误文档 → failed + errors 非空；xelatex 缺失路径用注入）
- [ ] **Step 2: RED** → **Step 3: 实现** → **Step 4: GREEN**（注：真实编译需 MiKTeX 写 %LOCALAPPDATA%，受限令牌下可能被拒——若失败属环境限制，控制器/用户升级权限复跑；测试本身带 `skipif` 当 xelatex 缺失）→ **Step 5: 提交**（消息 `feat: add latex build with structured report`）

### Task 4: LaTeX 静态检查 lint

**Files:**

- Create: `toolkit/src/cumcm_toolkit/latex/lint.py`
- Create: `toolkit/tests/latex/test_lint.py`

**Interfaces:**

- `lint_paper(work_dir: Path) -> dict[str, object]`：返回 `{status, issues:[{severity, kind, line, message}]}`；检查：未使用/未定义的 `\label`（有 `\label` 无 `\ref` 记 info；有 `\ref` 无 `\label` 记 error）、重复 label、`\cite` 无对应 bib 条目（error，留给 citation_check 详查则记 warning）、`TODO`/`待补充` 等占位标记（error）、`\includegraphics` 引用缺失文件（error）、未转义 `%` 等明显问题（warning）；空文档 → `{status: "ok", issues: []}` 语义可辩护（记 info）。

- [ ] **Step 1: 失败测试**（构造含各类问题的临时 tex：重复 label、ref 无 label、占位标记、缺失图片 → 对应 issues；干净文档 → 无 error）→ **Step 2: RED** → **Step 3: 实现**（正则解析，不依赖 TeX 引擎）→ **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add latex lint`）

### Task 5: PDF 结构化检查 pdf/inspect

**Files:**

- Create: `toolkit/src/cumcm_toolkit/pdf/inspect.py`
- Create: `toolkit/tests/pdf/test_inspect.py`

**Interfaces:**

- `inspect_pdf(pdf_path: Path) -> dict[str, object]`：用 **pypdf** 读取；返回 `{status, pages, blank_pages:[int], fonts:[{name, embedded}], metadata:{...}, errors}`；逐页 `extract_text()` 空白判定空白页（页号 1-based）；字体列表去重（含 embedded 标志，pypdf 的 `/Font` 资源解析尽力而为，无法解析时该字体记 `embedded: null` 不猜测）；`pypdf` 缺失或文件损坏 → `ValueError`。
- 新增依赖 `pypdf>=4,<7`（pyproject + uv lock/sync）。

- [ ] **Step 1: 失败测试**（用 pypdf 手工构造或复用 Task 3 编译出的 PDF：页数、空白页、字体字段；损坏文件 → ValueError；无 pypdf 环境 → skipif 或注入）→ **Step 2: RED** → **Step 3: 实现** → **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add pdf inspection`）

### Task 6: 证据链接 evidence/linker

**Files:**

- Create: `toolkit/src/cumcm_toolkit/evidence/linker.py`
- Create: `toolkit/tests/evidence/test_linker.py`

**Interfaces:**

- `link_claim(*, claim_id: str, claim_text: str, artifact_id: str, experiment_id: str, locator: dict[str, str], boundary: str) -> dict[str, object]`：生成符合 Phase 0 `evidence-link.schema.json` 的记录（schema_version "1.0"、claim_id `^clm_[...]`、locator `{kind, value}`、boundary 非空）；用 `make_validator` 校验，失败抛 `ValueError`。
- `link_claim_to_metrics(claim_id, claim_text, experiment_record: dict, metric_keys: list[str], boundary) -> dict`：从实验记录的 `metrics` 取数值生成定位（`locator={"kind": "metric", "value": "<key>"}`），claim_text 需含该数值（否则抛 ValueError——"数值可解析到证据"语义的 toolkit 侧表达）。
- `resolve_numeric_claims(abstract_text: str, links: list[dict]) -> dict[str, object]`：返回 `{claims:[{claim_id, number, in_abstract, in_evidence}], unresolved:[{number, ...}]}`；对 abstract 中的每个数字（正则 `\d+(\.\d+)?`），检查是否有某条 link 的 claim_text 或关联 metrics 值匹配；未匹配数字进 `unresolved`；`unresolved` 非空时 `status="failed"`（fail-closed——摘要数值必须可解析）。

- [ ] **Step 1: 失败测试**（合法 claim → schema 校验通过；locator 缺 value → ValueError；metrics 绑定含数值 → resolve 成功；摘要含未绑定数字 → unresolved + failed）→ **Step 2: RED** → **Step 3: 实现**（复用 scripts.validate_contracts）→ **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add evidence linker`）

### Task 7: 引用链接 evidence/citation_linker

**Files:**

- Create: `toolkit/src/cumcm_toolkit/evidence/citation_linker.py`
- Create: `toolkit/tests/evidence/test_citation_linker.py`

**Interfaces:**

- `link_citation(*, citation_id: str, claim_id: str, source_id: str, usage: str, locator: dict[str, str], support_boundary: str, verified_at: str) -> dict`：生成符合 Phase 0A `citation-link.schema.json` 的记录并校验。
- `link_approved_source(*, source_record: dict, claim_id: str, usage: str, locator: dict, support_boundary: str) -> dict`：`source_record["verification_status"] != "approved"` 或缺 `decision_id` → `ValueError`（只允许已批准来源）；`citation_id` 自动派生（`cite_` + hash）。
- `approved_sources(records: list[dict]) -> list[dict]`：过滤 approved 来源（含 decision_id）。

- [ ] **Step 1: 失败测试**（approved → 成功；candidate/rejected → ValueError；approved 缺 decision_id → ValueError；自动 citation_id 确定性）→ **Step 2: RED** → **Step 3: 实现** → **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add citation linker`）

### Task 8: BibTeX 生成与引用校验

**Files:**

- Create: `toolkit/src/cumcm_toolkit/latex/bibliography.py`
- Create: `toolkit/src/cumcm_toolkit/latex/citation_check.py`
- Create: `toolkit/tests/latex/test_bibliography.py`
- Create: `toolkit/tests/latex/test_citation_check.py`

**Interfaces:**

- `bibtex_entry(source: dict) -> str`：approved 来源 → BibTeX `@article{<key>, ...}`（key = `src_` 派生，如 `src_<hash8>`；字段 title/author/year/venue→journal、doi、url 按存在映射；不编造缺失字段）；`@misc` 当无 venue。
- `generate_bibliography(sources: list[dict]) -> str`：多条目 + 头部注释。
- `citation_check(tex_text: str, bib_text: str, citations: list[dict]) -> dict[str, object]`：返回 `{status, missing_bibtex:[...], unapproved_sources:[...], uncited_entries:[...], unmatched_citations:[...], errors}`；规则：`\cite{a,b}` 展开的每个 key 必须存在于 bib 条目；bib 条目必须对应一条 citation-link（citations 列表）；每条 citation 的 source 必须 approved；`\cite` 的 key 必须出现在 citations 中；任一项失败 → `status="failed"`。

- [ ] **Step 1: 失败测试**（bibtex_entry 字段映射与 key 确定性；generate 多条目；citation_check：正常 → ok；cite 无 bib 条目 → missing_bibtex；bib 条目无 citation → uncited；cite 无 citation-link → unmatched；来源未批准 → unapproved）→ **Step 2: RED** → **Step 3: 实现** → **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add bibliography and citation check`）

### Task 9: 端到端论文管线测试

**Files:**

- Create: `tests/e2e/test_paper_pipeline.py`

**Interfaces（验证 Phase 4 退出标准 1-5）:**

- 链路：① 造实验记录（用 Phase 1 `create_experiment_record`，metrics 含已知数值）与 approved 来源（用 Phase 0A `literature-source` 形状，approved + decision_id）→ ② `scaffold_paper` 建论文工程 → ③ 写入证据绑定正文：摘要含实验数值（来自 metrics），正文含 `\cite{key}`（来自 approved 来源）与 `\ref` → ④ `build_paper`（xelatex 双遍；**需升级权限跑 MiKTeX，控制器/用户执行**）→ ⑤ `lint_paper` + `citation_check` + `inspect_pdf` → ⑥ 断言：build ok、pages ≥ 1、无 undefined 引用；lint 无 error；citation_check ok（cite↔bib↔citation-link↔approved 一一对应）；inspect 结构化报告含 pages/blank_pages/fonts；摘要数值经 `resolve_numeric_claims` 全部解析（unresolved 为空）。
- 人工门 3 的 toolkit 侧表达：管线在"未提供 approved 来源"时必须在 citation 阶段失败（`link_approved_source` 拒绝未批准来源）。

- [ ] **Step 1: 写失败 e2e 测试** → **Step 2: RED**（缺模块）→ **Step 3: 补齐实现/修复缺陷**（保持 fail-closed）→ **Step 4: GREEN + 全量回归**（latex 相关部分若受限令牌失败，控制器/用户升级权限复跑）→ **Step 5: 提交**（消息 `test: add evidence-bound paper pipeline e2e`）

### Task 10: Phase 4 验收、主计划更新与交接

**Files:**

- Modify: `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`

**Interfaces:**

- 产出干净提交哈希与 Codex 轨道的已验证输入；不实现 `adapters/codex/skills/paper-*`。

- [ ] **Step 1: 完整验证**（`toolkit/tests/latex toolkit/tests/pdf toolkit/tests/evidence -v`；`tests/e2e/test_paper_pipeline.py -v`；全量 `toolkit/tests tests/contracts tests/knowledge tests/e2e -q`；validator；latex 相关若受限令牌失败 → 控制器/用户升级权限复跑后确认）
- [ ] **Step 2: 标记扫描 + `git diff --check` + `git status`**
- [ ] **Step 3: 主计划更新**：Phase 4 章节追加 `**Verified inputs (2026-08-22):**` 块（模板路径、写作知识 6 篇、八模块接口、e2e 管线、pypdf 依赖、11 契约不变；并注明 `adapters/codex/skills/paper-*` 属 Codex 轨道，主计划 Phase 4 tracking 行待双轨道合拢后标记完成——**不勾选 tracking 行**）。主计划结尾"下一步是编写并审批阶段 3 详细计划"→"下一步是编写并审批阶段 4 详细计划"？——**不改**：Phase 3 由 Codex 轨道推进，结尾句仍指 Phase 3；在 Phase 3 章节追加一行"（Codex 轨道执行中，Phase 4 工具核心已并行交付）"可选。若改动了任何测试钉住的措辞，同步更新 `tests/contracts/test_paper_integration_documentation.py`。
- [ ] **Step 4: 提交**（消息 `docs: record phase 4 toolkit inputs for codex track`）
- [ ] **Step 5: 交接报告**：最终提交哈希；八模块接口签名；模板与知识路径；e2e 管线路径；Codex 轨道消费清单（scaffold/build/lint/citation_check/inspect/linker/citation_linker/bibliography 接口 + 契约）；显式声明未实现 `adapters/codex/skills/paper-*` 与 DSH 插件。

## Completion criteria

- 第三个人工门的 toolkit 侧表达生效（未批准来源在引用链路被拒）。
- 摘要中的每个关键数值可解析到证据 ID（`resolve_numeric_claims` 无 unresolved；e2e 断言）。
- BibTeX/LaTeX 引用只来自已批准 `literature-source`，`citation_check` 校验正文/参考文献/定位/citation-link 一一对应。
- LaTeX 编译无阻断错误、未定义引用或缺失图片（build + lint 结构化报告）。
- PDF 页数、字体、空白页检查产生结构化报告（inspect_pdf）。
- 全部测试通过、验证器 11 契约零错误、工作树干净、主计划记录工具核心输入。
- 未实现 `adapters/codex/skills/paper-*`（明确属 Codex 轨道）。

## 交接输入（Codex 轨道/Phase 5 规划消费）

- `scaffold_paper`/`build_paper`/`lint_paper`/`citation_check`/`inspect_pdf`/`link_claim`/`link_approved_source`/`generate_bibliography` 接口。
- `shared/templates/latex/cumcm/` 模板与 `shared/knowledge/writing/` 六篇知识。
- `tests/e2e/test_paper_pipeline.py` 作为 Codex `paper-outliner/paper-writer/latex-publisher` 的黄金场景。
- 11 契约不变；pypdf 依赖入锁。
