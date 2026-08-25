# Phase 7 → Phase 8 交接说明

Phase 7（DSH 适配）已完成：cumcm-tools（15 工具）、literature-tools（3 工具）、12 个 DSH SKILL.md 镜像、preset cumcm-agent、双端资产奇偶基线与真实组合 e2e 全部通过。Phase 8（真题回归）的稳定输入为：阶段 6 交付的 `review-bundle`、`workflow-event`、`decision` 2.0 契约与磁盘工作流检查点，以及本阶段固化的双端资产哈希基线。

**部署限制（如实声明）**：本仓库静态路由与 Loader 真实组合测试通过，不等于目标 DSH 运行时中的真实 Agent 已经观察到相同的触发与权限行为；DSH 真实 Agent 前向观测仍是部署门。

## 一、插件安装与配置

两个插件均为薄 TS 适配器 + 子进程调用 Python CLI（单一事实来源在 `toolkit/src/cumcm_toolkit/`），安装方式同为 `dsh plugin --profile <name> add <本地包路径>`（本机 npm registry 不可达，采用 `link:` 本地路径 + junction 复用插件自带 node_modules，全程离线）。

```powershell
# 安装（本地路径，离线）
node C:\nvm4w\nodejs\node_modules\@deepseek-ai\dsh\lib\bin.js plugin --profile <name> add link:<worktree>\adapters\dsh\plugins\cumcm-tools
node C:\nvm4w\nodejs\node_modules\@deepseek-ai\dsh\lib\bin.js plugin --profile <name> add link:<worktree>\adapters\dsh\plugins\literature-tools

# 校验组合
node C:\nvm4w\nodejs\node_modules\@deepseek-ai\dsh\lib\bin.js --profile <name> --dump-config
```

配置以 profile 用户层 `cordis.patch.yml` 覆盖（整段替换，需重述所有键），或直接用 preset：

```powershell
# preset cumcm-agent（patch 层，顶层 - insert: 组合两插件）
node C:\nvm4w\nodejs\node_modules\@deepseek-ai\dsh\lib\bin.js --profile <name> --patch <worktree>\adapters\dsh\presets\cumcm-agent\cordis.yml --dump-config
```

**配置键约定（fail-closed，缺必需 → 启动失败，绝不静默降级）**：

| 插件 | 键 | 语义 |
| --- | --- | --- |
| cumcm-tools | `cumcmRoot` | REQUIRED：仓库根（含 .venv 与 toolkit/src）。子进程以其为 cwd，注入 `PYTHONPATH=<cumcmRoot>/toolkit/src;<cumcmRoot>` |
| cumcm-tools | `pythonBin` | 显式 python 绝对路径（可选，优先于 .venv）；空则回退 `.venv/Scripts/python.exe` → `uv run` → 抛错。双空且 `uv` 不在 PATH → 启动期桥接抛明确错误；`uv` 在 PATH 时回退 `uv run`，工具调用仍 fail-closed |
| cumcm-tools | `toolTimeoutMs` | 每次子进程超时毫秒（默认 120000） |
| literature-tools | `sourceRoot` | REQUIRED：仓库根（含 toolkit/src）。缺失或空 → Config schema 拒绝 + `apply()` 拒绝运行（启动失败）；子进程 cwd + `PYTHONPATH=<sourceRoot>/toolkit/src;<sourceRoot>` |
| literature-tools | `backend` | 搜索后端标识；空 = 无后端 → `literature_search` blocked |
| literature-tools | `allowedDomains` | 网络允许域白名单；本版本无真实后端转发，门禁采用 fail-closed 令牌语义（白名单须显式包含 backend 标识） |

python 解析顺序（cumcm-tools `resolvePython`）：`pythonBin` → `cumcmRoot/.venv` → `uv` on PATH → 抛错。literature-tools 子进程：`LITERATURE_TOOLS_PYTHON` env → `sourceRoot/.venv` → PATH `python`。

## 二、DSH Skill 部署（12 个 SKILL.md）

`adapters/dsh/skills/<name>/SKILL.md` 共 12 个，目录名与 Codex catalog（catalog_version 1.0）逐一精确一致：

`problem-reader`、`data-auditor`、`model-selector`、`solver`、`sensitivity-analyst`、`literature-researcher`、`model-reviewer`、`repro-reviewer`、`paper-reviewer`、`red-team-reviewer`、`submission-auditor`、`cumcm-orchestrator`

- 每份含 Overview / When to Use / Do Not Use / Workflow / Failure Closure / Handoff Contract / Quick Reference / Common Mistakes，Handoff Contract yaml 经程序化校验齐备（8 个 modeling-handoff 基础字段；5 个 review Skill + submission-auditor 含 decision_status/input_digest/rubric_digest；orchestrator 含 next_action）。
- 每个目录仅 SKILL.md（无 resources.json/agents）。挂载方式：按 DSH Skill 目录机制放入目标运行时 skills 目录（如 `%DSH_HOME%\skills\<name>\SKILL.md`），目录名保持与 frontmatter `name` 一致；工具面为 cumcm-tools / literature-tools 插件。
- 语义边界已在 SKILL.md 内声明：solver 执行面限 registry 三模型（linear-regression / decision-tree / kmeans），其余 plan-only；literature-researcher 无真实网络检索后端（无后端 → blocked、候选恒为空）；review 逻辑由 `cumcm_toolkit.review.*` 承担、不暴露为 DSH 工具（人工门纪律）；workflow 状态机由 `cumcm_toolkit.workflow.*` 承担、不暴露为 DSH 工具。

## 三、双端奇偶基线（Phase 8 引用）

- **model-cards**：33 个文件在 Codex 打包器（`package_codex_skills.py`）与 DSH manifest（`package_dsh_assets.py`）间集合相等、逐路径 SHA-256 一致。
- **契约**：15 项 schema + catalog.json（共 16 文件）双端覆盖与哈希一致；catalog_version 与 contract ids 同源断言（`test_catalog.py` 的 `EXPECTED_CONTRACT_IDS`）。`decision.schema.json` 为 v1/v2 双版本 oneOf（v2 为 legacy 迁移分支），奇偶测试按 {"1.0","2.0"} 断言。
- **关键产物形状**：modeling-handoff（12 artifact_type 最小记录过 schema）、experiment（schema required 12 字段 == 库产出键集）、review-report（schema required 14 字段 == `engine.review` 产出键集）语义一致。
- **资产清单**：`package_dsh_assets.py --check` 101 项资产无漂移（contracts 16 / templates 10 / knowledge 56 / model-cards 33 / workflow 20，去重后 101）。
- **handoff 形状**：12 份 SKILL.md 的 Handoff Contract yaml 字段 ⊆ schema 且 artifact_type 在 enum 内；8 基础字段齐备，扩展字段按 Skill 类型。

## 四、cumcm-tools 15 工具清单与契约对应

| # | 工具 | Python 模块 | 对应契约/形状 |
| --- | --- | --- | --- |
| 1 | `cumcm_data_profile` | `data.profile` | 画像报告（宽松对象，整数/数组字段） |
| 2 | `cumcm_data_transform` | `data.transform` | steps 变换报告（steps_applied/warnings） |
| 3 | `cumcm_model_run` | `models.runner` | registry 模型拟合（status/model/fitted/seed） |
| 4 | `cumcm_metrics` | `evaluation.metrics` | 回归/分类指标（metrics 开放对象） |
| 5 | `cumcm_sensitivity` | `evaluation.sensitivity` | 仅契约形状校验（base_params/perturb），不求值 |
| 6 | `cumcm_evidence_link` | `evidence.linker` | evidence-link 记录 |
| 7 | `cumcm_citation_link` | `evidence.citation_linker` | citation-link 记录（approved 门禁在库层强制） |
| 8 | `cumcm_latex_build` | `latex.build` | 编译报告（status/passes/pdf_path） |
| 9 | `cumcm_latex_lint` | `latex.lint` | lint 报告（status/issues） |
| 10 | `cumcm_citation_check` | `latex.citation_check` | 引用一致性报告（6 个数组字段） |
| 11 | `cumcm_pdf_inspect` | `pdf.inspect` | PDF 检查报告（页数/空白页/字体/元数据） |
| 12 | `cumcm_result_export` | `results.export` | 导出报告（status/path/format） |
| 13 | `cumcm_workspace_scaffold` | `project.scaffold` | 工作区（workspace_id/root/files） |
| 14 | `cumcm_experiment_record` | `experiments.manifest` | experiment 记录（schema required 12 字段） |
| 15 | `cumcm_artifact_index` | `artifacts.index` | 产物索引（数组） |

JSON 型参数一律声明为 string（CLI 收 argv 字符串）；输出按 stdout **最后一行** JSON 解析（容忍前置日志行）；argparse 失败（exit 2 + 空 stdout）归 failed 不崩溃；超时/取消/单流 >8MB 均 fail-closed。

## 五、literature-tools 3 工具与后端授权接口

| 工具 | 定位 | 状态 |
| --- | --- | --- |
| `literature_read_source` | 离线确定性解析 PDF/JSON/纯文本 → candidate（`verification_status: candidate`，缺项留空 + `metadata_gaps`，`content_sha256` 为文件字节真实哈希） | 已实现；.jsonl 显式拒绝（fail-closed）；PDF 为纯文本兜底最小提取（压缩/扫描可能为空，`extraction_note` 如实标注） |
| `literature_route_candidate` | 候选归一化分组 + 组内冲突标记 → `{groups, conflicts}`；规则在 Python `toolkit/src/cumcm_toolkit/literature/rules.py`，TS 侧零规则实现 | 已实现；单 argv ≤ ~20000 字符预检（分批建议 ≤~500 条/次） |
| `literature_search` | 搜索门禁（backend + allowedDomains）→ 授权占位 | **授权占位，后端转发未实现**：通过门禁返回 `{"status":"requires-user-authorization","candidates":[]}`，candidates 恒为空，绝不伪造检索结果 |

接入真实后端时：`allowedDomains` 应从令牌语义改为校验实际域名；凭据经 DSH 凭据机制引用，不写死。

## 六、遗留项（Phase 8 关注）

1. **原型 cumcm-paper 可被 cumcm-tools 替换**：用户目录 `E:\skill\plugins\cumcm-paper` 的原型插件未被修改（TS 直实现 xelatex/escapeLatex 等与 Python toolkit 重复），Phase 7 未动它；DSH profile `web` 仍挂载原型。Phase 8 可用 cumcm-tools 替换或收敛重复逻辑（计划外的用户目录操作，需用户确认）。
2. **`模型/` 已清理**：仓库根 `模型/`（249KB PDF）已移除（prework 第 6 项遗留）。
3. **uv 环境分支（Task 6）**：`resolvePython` 的 `uv run` 分支（`uv` 在 PATH 时回退）已在 preset 注释与 `tests/snapshots/dsh/test_preset.py` 层 2 中用 stub 实测断言（uv 可用时 fail-closed 仍成立）。配置 cumcm-agent preset 时注意：仅当 `pythonBin` 与 `cumcmRoot/.venv` 都不可用时才走到 `uv run`，工具调用仍需 CLI 成功才返回结果。
4. **codex agents 哈希引用（Task 5）**：`package_dsh_assets.py` 的 workflow 分类含 `adapters/codex/skills/*/agents/openai.yaml` 12 个路径的**哈希引用**（DSH 不复制 codex 产物，只引用路径+哈希以反映 codex 侧变更漂移）；清单 `assets` 表共 101 个唯一路径。Phase 8 若改 codex agents，需同步重生成 DSH manifest，否则 `--check` 报漂移。
5. **preset 消费路径**：preset 是 patch 层（`- insert:`），部署目标为 profile overlay（profile patch 文件或 `--patch`）；若后续要直接作为 agent-presets roster（`agent.cordis.yml` 扁平行）使用，需要一层薄转换。Phase 8 无此项阻塞，但部署前需确认目标 DSH 运行时的 preset 消费路径。
6. **DSH 仓库侧门禁未跑**：主计划 Phase 7 验证块中的 `pnpm run test / test:coverage / test:snapshot / build / hygiene` 属于 DSH 仓库自检（harness checkout 只读取证），Phase 7 未在 DSH 仓库内执行；Phase 8 如需官方 checkout 验证再按 dsh-plugin-development 技能执行。

## 七、Phase 8 复跑命令

```powershell
# 全量回归（worktree 根）
$env:PYTHONDONTWRITEBYTECODE='1'
& ".venv\Scripts\python.exe" -m pytest toolkit/tests tests/contracts tests/knowledge tests/e2e -p no:cacheprovider -q
& ".venv\Scripts\python.exe" scripts/validate_contracts.py                       # 15 契约 0 错

# 插件（worktree 内 node_modules 就位后原地运行）
& "C:\nvm4w\nodejs\node.exe" adapters\dsh\plugins\cumcm-tools\node_modules\typescript\bin\tsc -p adapters\dsh\plugins\cumcm-tools\tsconfig.json --noEmit
& "C:\nvm4w\nodejs\node.exe" adapters\dsh\plugins\cumcm-tools\tests\smoke.mjs    # 18 passed
& "C:\nvm4w\nodejs\node.exe" adapters\dsh\plugins\literature-tools\tests\smoke.mjs  # 25 passed

# 资产清单与奇偶/e2e
& ".venv\Scripts\python.exe" scripts/package_dsh_assets.py --check --output %TEMP%\dsh-assets  # 101 无漂移
& ".venv\Scripts\python.exe" -m pytest tests/contracts/test_codex_dsh_asset_parity.py tests/e2e/test_dsh_real_composition.py -v -p no:cacheprovider  # 20 passed
```

（注：沙盒内 tsc build 写 lib/ 被拒，已按先例在内容一致的 staging 副本构建并字节级核对；worktree 内 `lib/` 为已验证产物。）
