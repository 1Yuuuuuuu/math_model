# Phase 7 DSH 适配前置梳理（2026-08-22 实测基线）

> 目的：为 `docs/superpowers/plans/2026-08-21-cumcm-workbench-phase-7-dsh-adapter.md` 的编写提供输入与决策清单。本页只做盘点与决策点，不写详细计划。

## 1. 目标与范围（主计划 Phase 7 摘录）

- **Objective:** 在不复制开发源的前提下，为 DSH 提供同名 Skill、含显式网络权限的确定性搜索/读取 Tool 插件和真实组合测试。
- **Planned files:** `adapters/dsh/skills/`、`adapters/dsh/plugins/cumcm-tools/`、`adapters/dsh/plugins/literature-tools/`、`adapters/dsh/presets/cumcm-agent/cordis.yml`、`scripts/package_dsh_assets.py`、`tests/contracts/test_codex_dsh_asset_parity.py`、`tests/snapshots/dsh/`、`tests/e2e/test_dsh_real_composition.py`。
- **Exit criteria:** ① DSH 通过 Tool 插件暴露稳定、校验严格的模型可调用能力；② DSH 提供与 Codex 语义一致的 `literature-researcher`，搜索/读取用确定性 Tool，网络/允许域/凭据权限显式配置并失败关闭；③ `cordis.yml` 缺必需配置时明确失败；④ 产品可见插件通过 Loader 真实组合测试；⑤ Codex 与 DSH 共享资产哈希、契约版本和关键产物语义一致。

## 2. 输入盘点（Phase 1–6 可消费物）

| 输入 | 状态 | Phase 7 用途 |
| --- | --- | --- |
| 15 项契约（catalog） | 树内已登记（含 Phase 0/0A + modeling-handoff/review-report/review-bundle/workflow-event） | 工具输出 JSON 的校验基线；`test_codex_dsh_asset_parity` 的契约版本核对 |
| Python toolkit 22 模块 | 已实现（data/models/evaluation/results/latex/pdf/evidence/review/workflow） | DSH 工具的确定性核心（**单一事实来源**） |
| 33 张模型卡 + 11 篇基础 + 6 篇写作 + 文献三件套 | 已实现 | 打包进 DSH 资产（哈希奇偶） |
| Codex 12 Skill + 打包器 | **未提交**（Codex 轨道，含我审出的 Criticals） | `adapters/dsh/skills/` 的同名镜像基准；语义奇偶测试 |
| workflow 状态机 + 四个人工门 | 未提交（Phase 6，含恢复死锁） | DSH preset 的编排语义 |
| cumcm-paper 原型插件（本会话工具） | 已装（`link:E:/skill/plugins/cumcm-paper`） | Phase 7 插件形态的先例与**改造对象** |

## 3. DSH 运行时环境事实（本机实测，2026-08-22）

- `DSH_HOME = C:\Users\YU\.dsh`；profiles：`web`（活跃，bundle 层 = base + web-app + agent-teams + **cumcm-paper** + automode）。
- `cumcm-paper` 插件以 `link:E:/skill/plugins/cumcm-paper` 挂载；结构合规（package.json 双面 exports + `dsh.bundle.patch` + cordis.patch.yml + tsc build + peerDependencies `@deepseek-ai/{cordis,dsh-agent,dsh-session,dsh-tools,schemastery}`）。
- DSH CLI：`C:\nvm4w\nodejs\dsh.ps1`（**执行策略限制，需 `-ExecutionPolicy Bypass`** 才能跑 `dsh plugin` 等命令）。
- Harness checkout（证据源）：`C:\Users\YU\AppData\Local\nvm\v22.23.2\node_modules\@deepseek-ai\dsh`（只读分析用，按 dsh-plugin-development 技能 §2）。
- Skills 目录 `C:\Users\YU\.dsh\skills`：已有 `cumcm-paper`、`math-modeling-paper` 等（DSH agent 技能位）。
- 本会话 = DSH 环境（`DSH_WEB_URL: http://127.0.0.1:3080`），技能挂载机制已验证。

## 4. 现状与先例分析：cumcm-paper 原型插件

**结构合规**（§3），但存在一个 Phase 7 必须解决的架构问题：

- 原型工具在 **TS 侧直接实现**（`src/index.ts`：spawn xelatex/latexmk、`escapeLatex`、文件检查等），未消费 Python toolkit——`escapeLatex` 与 `toolkit/results/export.py:_latex_escape`、编译逻辑与 `toolkit/latex/build.py` **重复实现**。
- 这违背设计决策"推理与确定性分离 + 单一事实来源 + 不复制开发源"——TS 复刻会随 Python 侧演进而漂移。
- 结论：**Phase 7 的 `cumcm-tools` 插件应把原型重构为"薄 TS 适配器 + 子进程调用 Python CLI"**，或至少把重复逻辑收敛到 Python 侧；原型作为形态先例保留，逻辑不再重复。

## 5. 关键决策点（写详细计划前须拍板）

### D1 桥接策略（最高优先级）
- 选项 A（推荐）：**薄 TS 适配器 + 子进程调用 Python CLI**。插件配置新增 `cumcmRoot`（仓库根）与 `pythonBin`（.venv python 或 `uv run`），工具 spawn `python -m cumcm_toolkit.<module>` 并严格解析 JSON；输出经契约校验；任一失败 → 结构化 failed（fail-closed）。单一事实来源保持在 Python toolkit。
- 选项 B：TS 直实现（维持原型路线）——被"不复制开发源"否决，除非确无 Python 等价（TeX 引擎定位可留 TS 侧，但编译报告已由 `latex/build.py` 覆盖）。
- 需要：Phase 7 计划含"为缺 CLI 的模块补 `__main__`"任务（见 D2）。

### D2 工具面与 CLI 缺口
- 现有 CLI（6）：`data/profile`、`project/scaffold`、`latex/scaffold`、`experiments/manifest`、`artifacts/index`、`environment/doctor`。
- 需补 CLI 的确定性模块（设计文档 DSH 工具清单对应）：`data/transform`、`evaluation/metrics`、`evaluation/baselines`、`evaluation/sensitivity`、`evidence/linker`、`evidence/citation_linker`、`latex/build`、`latex/lint`、`latex/citation_check`、`latex/bibliography`、`pdf/inspect`、`results/export`（models/registry+runner 可视需要）。
- 每个新 CLI：稳定 JSON + exit 0/1 + `{"status":"failed","error":...}`（沿用既有模式），并配契约/JSON round-trip 测试。
- `review/*` 与 `workflow/*` 是否暴露为 DSH 工具需另行决策：评审/编排属 Skill 职责（DSH agent 调用 Skill + 少量工具），建议**不**直接暴露为通用工具（避免模型绕过人工门）。

### D3 literature-tools：网络权限与失败关闭
- 按 Phase 0A 政策：搜索需用户授权后端（`paper-search` CLI 当前不可用；runtime-search 需显式网络/允许域/凭据配置）。
- Phase 7 提供：**确定性读取/解析**（PDF/元数据读取、候选归一化、去重、来源评价——复用 `shared/knowledge/literature/` 规则）+ **路由**（候选→人工确认→引用）+ **失败关闭**（无后端/无授权 → blocked，不伪造）。
- 插件配置：`network.allowedDomains`、`network.secrets`（引用 DSH 凭据机制）、`backend`（空 = 仅离线整理）。`cordis.yml` 缺必需配置 → 启动失败（退出标准③）。

### D4 Skill 奇偶
- `adapters/dsh/skills/` 提供与 Codex 12 Skill 语义一致的同名 Skill（problem-reader/data-auditor/model-selector/solver/sensitivity-analyst/literature-researcher + 5 个评审 + cumcm-orchestrator）。
- `tests/contracts/test_codex_dsh_asset_parity.py`：共享资产哈希、契约版本、关键产物语义（handoff/实验记录/评审报告形状）双端一致。
- **前置阻塞**：Codex 12 Skill 尚未提交且含我审出的 Criticals（CR1/CR2/C1/IM2 + Phase 6 恢复死锁）——奇偶测试的"基准"不稳定，Phase 7 计划必须把"Codex 轨道先提交并修复"列为硬依赖。

### D5 打包
- `scripts/package_dsh_assets.py`：打包共享资产（契约/模板/知识/模型卡）到 DSH 侧，SHA-256 与 `package_codex_skills.py` 对齐（奇偶测试）。
- 资产放置：随插件分发（files）或按配置路径引用仓库（`cumcmRoot`）；推荐**配置路径引用仓库 + 哈希清单**（避免复制开发源、避免插件与仓库漂移）。

### D6 真实组合测试
- `tests/e2e/test_dsh_real_composition.py` + 按 dsh-plugin-development §8：`dsh plugin --profile <scratch> add` → `--dump-config` → Loader 真实启动 → 工具调用（本机真实 xelatex/Python）→ 断言用户可见表面。
- 在 DSH 仓库跑 `pnpm test/build/hygiene`（若需官方 checkout，按技能 §2.3 克隆 `deepseek-ai/deepseek-harness`，只读取证）。

### D7 preset
- `adapters/dsh/presets/cumcm-agent/cordis.yml`：组合 cumcm-tools + literature-tools + 同名 Skill 的预设；缺必需配置 → 明确失败。

## 6. 前置依赖与阻塞（Phase 7 计划编写前）

1. **Codex 轨道提交 + 修复**（硬依赖）：Phase 3/5/6 全部未提交；我审出的 Criticals（validate_contracts $ref、五 Reviewer 打包闭包、模型门接线、证据索引、Phase 6 恢复死锁）不解决，Phase 7 的"稳定 Skill 输入输出"与"双端奇偶"无法真实成立。
2. **主计划过期**：line 499"14 契约/11 Skill/下一步阶段 6"与 line 366"15/12 完成"矛盾；Phase 7 计划引用主计划前需清理（归 Codex/治理轨道）。
3. **CLI 缺口**：D2 的 12 个模块补 `__main__`（属 Phase 7 计划内任务，但可先行）。
4. **环境**：`dsh.ps1` 需 `-ExecutionPolicy Bypass`；官方 checkout 取证需克隆。
5. **杂散目录**：仓库根 `模型/`（249KB PDF）需移除或 gitignore（两轮审阅均标记）。
6. **原型重构**：cumcm-paper 原型从 TS 直实现改为薄适配器（或至少收敛重复逻辑），避免双端漂移。

## 7. 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Python CLI 契约与 DSH 工具校验漂移 | 双端不一致 | 契约校验同一套（15 契约）；奇偶测试锁哈希/形状 |
| 子进程环境（.venv/uv）在用户机器不可用 | 工具全部失败 | 插件配置显式指定 pythonBin/cumcmRoot；doctor 工具先行诊断；失败关闭 |
| 搜索后端授权缺失 | literature-researcher 不可用 | 离线整理 + 检索计划 + 明确授权路径（Phase 0A 政策） |
| Codex 轨道 Criticals 未修 | 奇偶测试假绿或不可运行 | 把 Codex 提交+修复列为 Phase 7 前置门 |
| 人工门被 DSH 工具绕过 | 审批失效 | review/workflow 不作为通用工具暴露；编排走 Skill + 四门纪律 |

## 8. 写详细计划前须拍板的清单

- [ ] D1 桥接：确认"薄 TS 适配器 + Python CLI 子进程"路线（推荐）vs 其他。
- [ ] D2 工具面：12 个补 CLI 的模块清单；review/workflow 是否暴露（建议不）。
- [ ] D3 网络权限：allowedDomains/凭据/backend 配置形态；无后端语义。
- [ ] D5 资产：配置路径引用仓库 + 哈希清单（推荐）vs 随插件分发。
- [ ] 前置门：是否把"Codex Phase 3/5/6 提交 + Criticals 修复"设为 Phase 7 开工硬条件。
- [ ] 原型处置：cumcm-paper 重构为适配器（Phase 7 内）或保留 TS 直实现（记录为已知偏差）。
