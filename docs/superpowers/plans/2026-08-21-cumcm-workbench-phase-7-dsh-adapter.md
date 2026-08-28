# Phase 7 DSH 适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不复制开发源的前提下，为 DeepSeek Harness 交付同名 Skill、cumcm-tools 与 literature-tools 两个 Tool 插件、cumcm-agent 预设、打包与双端奇偶测试、真实组合测试。

**Architecture:** 确定性核心留在 Python toolkit（单一事实来源）；`adapters/dsh/plugins/cumcm-tools/` 是**薄 TypeScript 适配器**——每个工具 spawn `python -m cumcm_toolkit.<module>` 子进程并严格解析 JSON，输出经 15 项契约校验，失败关闭；`literature-tools` 提供确定性读取/解析/路由，网络允许域与凭据显式配置、无后端即 blocked；`adapters/dsh/skills/` 镜像 Codex 12 Skill 的语义（奇偶测试锁哈希与形状）；`scripts/package_dsh_assets.py` 打包共享资产并与 `package_codex_skills.py` 对齐。

**Tech Stack:** TypeScript 5.9、Node ≥20、pnpm、`@deepseek-ai/{cordis,dsh-agent,dsh-session,dsh-tools,schemastery}`（peer，从原型插件/官方 checkout 取证版本）、tsc 双 program（host 单面，本插件无 client）、Python 3.11 + uv（子进程侧）、pytest、JSON Schema 15 契约。

**Spec:** `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（Phase 7 章节，第 400–440 行）、`docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`（DSH 适配层、工具体系）、`docs/operations/phase7-dsh-prework.md`（前置梳理，D1-D7 决策）。

## Global Constraints

- **不复制开发源**：DSH 工具不得在 TS 侧重写 toolkit 逻辑（现有 cumcm-paper 原型的 TS 直实现是反例，须重构为薄适配器）；确定性行为一律走 Python CLI。
- 输出必须经契约校验（15 项）；任一失败 → 结构化 `{"status":"failed","error":...}` + exit 1（fail-closed），不猜测。
- literature-tools：搜索需用户授权后端；网络允许域与凭据显式配置；无后端/无授权 → blocked，不伪造元数据；候选≠引用（Phase 0A 政策）。
- `cordis.yml`/插件配置缺必需项 → 启动失败（不静默降级）。
- 人工门纪律：`review/*` 与 `workflow/*` **不**暴露为通用 DSH 工具（防模型绕过）；编排走 Skill。
- 共享资产以配置路径引用仓库 + SHA-256 哈希清单，不把 `shared/` 复制进插件包。
- 每个任务独立提交并通过新鲜评审；先 RED 后 GREEN；变更面驱动验证，Task 8 里程碑完整回归。
- 本阶段不修改 `adapters/codex/*`（Codex 轨道）；不实现 Phase 8 内容。
- 沙盒事实：git 提交由控制器执行（自动评审时批时获批）；评审者用只读 git 自取 diff；测试用绝对路径 + `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider`；`dsh.ps1` 需 `-ExecutionPolicy Bypass`。

## 已探测的环境事实（2026-08-22，Phase 7 计划输入）

| 项 | 实测 |
| --- | --- |
| 仓库状态 | `main` = `8b9b807`（Codex Phase 3/5/6 已提交；**未推送 origin**，`origin/main` = `589e21e`）；工作树干净；全量 656 通过；验证器 15 契约 0 错 |
| Python 侧 | 22 模块；**6 个有 CLI**（profile/project-scaffold/latex-scaffold/manifest/index/doctor），12 个确定性模块缺 CLI（Task 1 补） |
| DSH 环境 | `DSH_HOME=C:\Users\YU\.dsh`；`profiles/web` 活跃（bundle：base+web-app+agent-teams+cumcm-paper+automode）；`dsh` CLI 在 `C:\nvm4w\nodejs\dsh.ps1`（需 Bypass）；Harness checkout `C:\Users\YU\AppData\Local\nvm\v22.23.2\node_modules\@deepseek-ai\dsh` |
| 原型插件 | `E:\skill\plugins\cumcm-paper`（link 挂载；TS 直实现 cumcm_scaffold/latex_check/submission_check；package.json 结构合规、peer `@deepseek-ai/{cordis^4,dsh-agent^0.1.0-rc.6,dsh-session,dsh-tools,schemastery^3.18}`；pnpm-lock 存在） |
| Node 工具链 | Node ≥20（nvm4w）；pnpm 可用性以 `pnpm --version` 实测为准；TS 5.9 |
| 杂散项 | 仓库根 `模型/`（249KB PDF，未 gitignore）——Task 0 清理 |

## 本计划的设计决策（Ruling，前置梳理 D1-D7 定案）

1. **D1 桥接 = 薄 TS 适配器 + 子进程调 Python CLI**。插件配置 `cumcmRoot`（仓库根）、`pythonBin`（.venv python 绝对路径或 `uv run` 前缀数组）；工具 spawn `python -m cumcm_toolkit.<module> <args>`（cwd=cumcmRoot，`PYTHONDONTWRITEBYTECODE=1`），解析 stdout JSON（严格），非 0 exit → failed。子进程超时与信号透传。**不在 TS 侧重写任何 toolkit 逻辑**。
2. **D2 工具面**：12 个确定性模块补 `__main__`（Task 1）；`review/*`、`workflow/*` 不暴露。工具清单（设计文档 DSH 工具对应）：`cumcm_data_profile`、`cumcm_data_transform`、`cumcm_model_run`、`cumcm_metrics`、`cumcm_sensitivity`、`cumcm_evidence_link`、`cumcm_citation_link`、`cumcm_latex_build`、`cumcm_latex_lint`、`cumcm_citation_check`、`cumcm_pdf_inspect`、`cumcm_result_export`、`cumcm_workspace_scaffold`、`cumcm_experiment_record`、`cumcm_artifact_index`（后三个已有 CLI）。
3. **D3 literature-tools**：工具 `literature_read_source`（PDF/元数据解析，离线）、`literature_route_candidate`（候选→人工确认→引用，复用 shared/knowledge/literature 规则）、`literature_search`（仅当 backend 配置；`network.allowedDomains` + 凭据引用 + `backend` 配置；无配置 → blocked）。
4. **D4 Skill 奇偶**：`adapters/dsh/skills/` 12 个 SKILL.md 镜像 Codex 语义；奇偶测试断言：共享资产哈希、契约版本、handoff/实验记录/评审报告关键形状一致（不要求逐字相同）。
5. **D5 打包**：`package_dsh_assets.py` 生成资产清单（契约/模板/知识/模型卡）SHA-256 清单 + 与 `package_codex_skills.py` 对齐；DSH 插件运行时按 `cumcmRoot` 引用仓库资产（哈希校验），不复制进包。
6. **D6 真实组合**：`tests/e2e/test_dsh_real_composition.py`：scratch profile → `dsh plugin --profile <scratch> add <本地路径>` → `--dump-config` 断言插件层 → Loader 启动 → 真实调用 2-3 个工具（本机 python+xelatex）→ 断言输出形状与失败关闭。
7. **D7 preset**：`adapters/dsh/presets/cumcm-agent/cordis.yml` 组合两插件 + 配置（cumcmRoot/pythonBin/allowedDomains/backend 占位必填），缺必需配置 → 启动失败测试。
8. **原型处置**：cumcm-paper 原型**不在本阶段修改**（E:/skill/plugins 用户目录），但 cumcm-tools 插件必须避免其 TS 直实现模式；交接报告注明原型可被 cumcm-tools 替换。

## File structure and ownership

| 文件 | 单一职责 |
| --- | --- |
| `toolkit/src/cumcm_toolkit/<12 模块>` | 补 `__main__` CLI（稳定 JSON + exit 0/1） |
| `toolkit/tests/<对应>` | CLI 契约/round-trip 测试 |
| `adapters/dsh/plugins/cumcm-tools/{package.json,cordis.patch.yml,tsconfig.json,src/index.ts,src/bridge.ts,README.md,tests/}` | 薄 TS 适配器（15 个工具） |
| `adapters/dsh/plugins/literature-tools/{package.json,cordis.patch.yml,tsconfig.json,src/index.ts,README.md,tests/}` | 确定性读/解析/路由 + 网络配置 |
| `adapters/dsh/skills/<12 个 SKILL.md>` | Codex Skill 的 DSH 语义镜像 |
| `adapters/dsh/presets/cumcm-agent/cordis.yml` | preset 组合 + 必填配置校验 |
| `scripts/package_dsh_assets.py` | DSH 资产哈希清单（与 codex 打包器对齐） |
| `tests/contracts/test_codex_dsh_asset_parity.py` | 双端哈希/契约/形状奇偶 |
| `tests/snapshots/dsh/` | 资产清单快照 |
| `tests/e2e/test_dsh_real_composition.py` | Loader 真实组合 + 工具调用 |
| `docs/operations/phase7-dsh-prework.md` | 前置梳理（本计划依据） |

## Execution preflight: 分支与工具链

1. worktree 分支（如 `.worktrees/phase-7-dsh-adapter -b phase-7-dsh-adapter`）；`uv sync --dev`（worktree .venv）。
2. Node 工具链核验：`node --version`、`pnpm --version`（缺则用 `corepack enable` 或 npm 全局）；TS 编译器可用性。
3. 清理仓库根 `模型/` 目录。
4. 取证 `@deepseek-ai/*` peer 版本：从原型插件 package.json 与 Harness checkout 的 node_modules 实际版本核对（不猜）。

---

### Task 0: 清理与基线

- 删除仓库根 `模型/` 目录；`git status` 确认仅 Phase 7 文件。
- 全量回归基线（656 通过 + 验证器 15/0）记录于报告。

### Task 1: 12 个 Python 模块补 CLI 入口（TDD）

**Files:** 各模块加 `main()` + `if __name__ == "__main__":`；`toolkit/tests/<模块>/test_<模块>_cli.py`。

**接口约定（统一）:** CLI 输入为必要参数（路径/JSON 文件或 inline JSON），输出单行稳定 JSON（`sort_keys=True, ensure_ascii=True, allow_nan=False`）；成功 exit 0；任何失败 exit 1 + `{"status":"failed","error":...}`。**不接受 stdin 交互；参数从 argv 读**（子进程桥接友好）。

模块与参数设计（沿用各模块库签名）：
- `data.transform --input <csv> --steps <json> --output <csv>`（读 CSV → transform_dataframe → 写回 + 报告 `{steps_applied, warnings}`）
- `evaluation.metrics --kind regression|classification --y-true <json> --y-pred <json> [--positive-label]` → `{metrics}` 或失败
- `evaluation.baselines --strategy <m> --y <json>` → `{strategy, value}`；`--compare` 模式输出 improvement
- `evaluation.sensitivity --base-params <json> --perturb <json>`（evaluate 回调无法从 CLI 注入——**裁决**：CLI 仅支持"由输入 JSON 指定 evaluate 描述符"太重，改为仅暴露 `--validate <json>` 模式：校验 sensitivity_report 契约形状；真正 evaluate 由调用方库函数承担，DSH 工具不暴露 sensitivity 求值，改暴露 `cumcm_sensitivity` 仅做报告校验——在计划中标注为已知边界）→ **简化：CLI 校验模式 + 报告库函数留给 Codex/DSH 上层**。若实现者认为可注入纯函数 JSON 表达式（如 `"a*10+b"` 求值器）更实用，可提方案（eval 有安全风险，默认不做）。
- `evidence.linker --claim <json>` → 校验并输出 evidence-link 记录
- `evidence.citation_linker --source <json> --claim-id ...` → 输出 citation-link（approved 门禁在库层已强制）
- `latex.build --dir <path> [--passes 2]` → 结构化报告
- `latex.lint --dir <path>` → 结构化报告
- `latex.citation_check --tex <path> --bib <path> --citations <json> --approved-source-ids <json>` → 结构化报告
- `latex.bibliography --sources <json>` → 输出 BibTeX 文本
- `pdf.inspect --pdf <path>` → 结构化报告
- `results.export --json <data-json> --out <path>` / `--csv <rows-json>` / `--latex` → 写文件 + 报告

每个 CLI：RED（模块无 main/输出错）→ GREEN；全部跑契约回归。

**注**：本任务量大，实现者按模块分组推进，每组独立 RED→GREEN；报告逐模块记录。

### Task 2: cumcm-tools 插件（薄 TS 适配器）

**Files:** `adapters/dsh/plugins/cumcm-tools/{package.json,cordis.patch.yml,tsconfig.json,src/index.ts,src/bridge.ts,README.md,tests/smoke.mjs}`。

**接口:**
- package.json：参照原型结构（双面 exports、`dsh.bundle.patch`、peer `@deepseek-ai/*`，版本从取证结果）；`"files": ["lib","cordis.patch.yml","README.md"]`。
- cordis.patch.yml：`id: cumcm-tools`，config 默认 `{cumcmRoot: '', pythonBin: '', toolTimeoutMs: 120000}`。
- `src/bridge.ts`：`runPythonTool(config, moduleArgs: string[]) -> Promise<{ok: boolean, data: unknown, error?: string}>`——`spawn(pythonBin 或 ["uv","run"], ['-m','cumcm_toolkit.'+module, ...args], {cwd: cumcmRoot, env: {PYTHONDONTWRITEBYTECODE:'1', ...}})`；超时 kill；stdout 末行 JSON 解析；exit≠0 → failed。`resolvePython()`：config.pythonBin 非空用之；否则尝试 `cumcmRoot/.venv/Scripts/python.exe` 与 `uv run`（按序，全缺 → 明确错误）。
- `src/index.ts`：`inject=['tools']`；注册 **15 个工具**（Task 1 清单 + 3 个既有），每个 `defineTool`：description 写明前置条件（cumcmRoot/pythonBin 可用、输入契约）、parameters（value-schema DSL）、output.schema（对应契约形状或宽松对象）、`output.render` 稳定文本；工具 body 调 bridge + 契约形状断言。
- tests：`tests/smoke.mjs` 用 `ctx.tools` 真实注册（或按 dsh-plugin-development §8 的最小组合）断言工具存在 + 一个工具对假 python 的失败关闭 + `--dump-config` 形状。
- **构建**：`tsc -p tsconfig.json`（host 单 program，无 client）；typecheck 通过；产物 lib/。

**裁决（环境）**：插件构建与测试需要 `@deepseek-ai/*` devDeps——优先从 Harness checkout 或原型 node_modules 复用（npm install 若网络可用亦可）；node_modules 不提交。

### Task 3: literature-tools 插件（确定性读/解析/路由）

**Files:** `adapters/dsh/plugins/literature-tools/{package.json,cordis.patch.yml,tsconfig.json,src/index.ts,src/rules.ts,README.md,tests/smoke.mjs}`。

**接口:**
- `literature_read_source --path <pdf|json>`：解析 PDF 文本/元数据或 JSON 记录 → 候选元数据（不补造 DOI/作者/年份；缺项保留空并标记）；输出候选对象（形状与 `literature-source` 契约的 candidate 状态兼容）。
- `literature_route_candidate --candidate <json>`：按 `shared/knowledge/literature/deduplication.md` 规则归一化（复用规则语义，**TS 侧重写规则引擎需与 Python 测试对齐——裁决：归一化规则在 Python 侧补一个 `toolkit/.../literature/` 小模块（Task 1 外新增），TS 只做参数转发**，避免规则双实现）；输出候选组 + 冲突标记（人工核验）。
- `literature_search --query ...`：仅当 `config.backend` 非空且域在 `allowedDomains` → 转发后端（如用户授权）；否则 blocked（明确错误）。凭据经 DSH 凭据机制引用，不写死。
- 配置：`{backend:'', allowedDomains:[], sourceRoot:''}`；缺必需（sourceRoot）→ 启动失败。

**裁决**：规则引擎收敛到 Python（新增 `toolkit/src/cumcm_toolkit/literature/rules.py`：`normalize_title`、`group_candidates`、`conflict_flags`，TDD 与 `tests/knowledge/test_literature_knowledge.py` 的参考实现对齐）；TS 插件转发。这是"不复制开发源"在文献规则上的落实。

### Task 4: DSH 12 Skill 镜像 + 奇偶

**Files:** `adapters/dsh/skills/<12 个 SKILL.md>`；`tests/contracts/test_codex_dsh_asset_parity.py`；`tests/snapshots/dsh/`。

- 12 个 SKILL.md：语义镜像 Codex（problem-reader/data-auditor/model-selector/solver/sensitivity-analyst/literature-researcher + 5 评审 + cumcm-orchestrator）；DSH 侧注明消费的 DSH 工具（cumcm_* 名）与 Python 库；不声称未实现能力。
- `package_dsh_assets.py`（Task 5 前置依赖）：生成共享资产 SHA-256 清单（契约/模板/知识/模型卡）+ Skill 清单。
- `test_codex_dsh_asset_parity.py`：① 资产哈希清单双端一致（codex 打包器 vs dsh 打包器）；② 契约版本一致（catalog 15）；③ 关键产物形状（handoff/experiment/review-report）语义一致（字段名/必填集）。

### Task 5: package_dsh_assets.py

**Files:** `scripts/package_dsh_assets.py`。

- 输出 `dist/dsh-assets/manifest.json`：资产路径 + SHA-256（契约/模板/知识/模型卡/Workflow yaml）；`--check` 模式：现有清单 vs 当前仓库哈希 → 漂移即 exit 1。
- 与 `package_codex_skills.py` 的资产覆盖范围对齐（奇偶测试依赖）。

### Task 6: preset cumcm-agent

**Files:** `adapters/dsh/presets/cumcm-agent/cordis.yml`。

- 组合 cumcm-tools + literature-tools；配置占位（cumcmRoot/pythonBin/allowedDomains/backend/sourceRoot）必填校验；缺必需 → 启动失败（测试：坏 cordis.yml → `--dump-config` 或 Loader 报错）。

### Task 7: 真实组合 e2e

**Files:** `tests/e2e/test_dsh_real_composition.py`。

- scratch profile（临时 DSH_HOME）：`dsh plugin --profile <scratch> add <cumcm-tools 本地路径>` → `--dump-config` 断言插件层与默认 config → Loader 启动（headless 或最小）→ 真实调用 2-3 个工具（如 cumcm_workspace_scaffold、cumcm_data_profile、cumcm_latex_build）→ 断言 JSON 形状 + 失败关闭（bad input → failed）。
- 环境标记：本机 `dsh.ps1` 需 `-ExecutionPolicy Bypass`；若 e2e 在受限沙盒不可运行（子进程/网络限制），报告 DONE_WITH_CONCERNS 并给确切错误，控制器/用户升级权限复跑。

### Task 8: Phase 7 验收、主计划更新与交接

- 完整验证：`pytest toolkit/tests tests/contracts tests/knowledge tests/e2e -q`；`validate_contracts.py`；插件 `pnpm typecheck && pnpm build`；`package_dsh_assets.py --check`；`test_codex_dsh_asset_parity.py`；`test_dsh_real_composition.py`（或环境限制记录）。
- 主计划：Phase 7 章节追加 Verified inputs；结尾"下一步是阶段 7 的 DSH 适配"→"阶段 8 的真题回归"（同步 `test_paper_integration_documentation.py` 钉住的断言）；Phase 7 tracking 行勾选（若全绿）。
- 交接：插件安装/配置文档；DSH Skill 部署说明；`cumcmRoot`/`pythonBin` 约定；与 Codex 轨道的奇偶基线；遗留（原型替换、模型/ 已清理）。

## Completion criteria

- 12 个 Python 模块 CLI 全部可用（稳定 JSON + fail-closed），测试覆盖。
- cumcm-tools 插件通过 typecheck/build/冒烟，15 工具注册，子进程桥接失败关闭。
- literature-tools 三工具就绪，无后端 blocked，规则引擎收敛于 Python（无 TS 重复实现）。
- 12 个 DSH Skill 镜像 + 奇偶测试通过（哈希/契约/形状）。
- package_dsh_assets.py `--check` 通过；preset 缺配置失败。
- 真实组合 e2e 通过（或环境限制如实记录并由升级权限复跑确认）。
- 全量回归 + 验证器 15 契约 0 错；主计划反映完成状态。

## 交接输入（Phase 8 规划消费）

- 插件安装命令与配置模板；DSH Skill 部署清单；双端奇偶基线；cumcm-tools 工具清单与契约对应；literature-tools 后端授权接口；原型替换建议。
