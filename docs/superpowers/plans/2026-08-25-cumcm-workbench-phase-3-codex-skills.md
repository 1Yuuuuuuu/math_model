# Phase 3 Codex 建模 Skills Implementation Plan

> **执行要求：** 使用 `writing-skills`、`skill-creator` 与测试先行；每个 Skill 独立完成 RED、GREEN、复核后再进入下一个。

**Goal:** 创建六个可发现、可组合、失败关闭且可确定性打包的 Phase 3 Codex 建模 Skills，形成可追溯建模半链路；仓库发行 catalog 后续可包含其他阶段的 Skill，当前第七个 `model-reviewer` 属 Phase 5。

**Architecture:** `adapters/codex/skills/` 保存轻量 Skill 源文件和资源声明，`shared/` 保存唯一知识源，打包器将二者组合成自包含产物。pytest 对发现描述、路由快照、边界、资源哈希和代表场景进行离线验证。

**Tech Stack:** Agent Skills、YAML、JSON、Python 3.11、pytest、现有 `cumcm_toolkit` API。

**Spec:** `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-3-codex-skills-design.md`

## 全局约束

- 不修改或复制 Phase 2 模型知识；只通过资源声明消费。
- 不新增网络依赖；文献路由测试完全离线。
- 不把 Skill 文档存在视为行为验证；契约测试必须先失败。
- 不将候选文献升级为批准引用。
- 不让不支持的模型进入执行成功状态。
- 所有路径使用仓库相对 POSIX 路径，打包器拒绝绝对路径和 `..`。

## Task 1：建立失败的 Skill 契约与路由快照

**Files:**

- Create: `tests/snapshots/codex-skills/routing-cases.yaml`
- Create: `tests/snapshots/codex-skills/test_skill_contracts.py`
- Create: `tests/e2e/test_literature_researcher_routing.py`

**Steps:**

1. 为六个 Phase 3 Skill 编写触发/不触发样例和预期边界；发行 catalog 后续新增 Skill 时同步扩展案例。
2. 编写测试，检查目录、frontmatter、`agents/openai.yaml`、必备章节、交接字段和 `resources.json`。
3. 编写文献后端优先级与无后端失败关闭测试。
4. 运行测试并确认因 Skill 尚不存在而失败。

## Task 2：创建并验证 `problem-reader`

**Files:** `adapters/codex/skills/problem-reader/{SKILL.md,agents/openai.yaml,resources.json}`

1. 按仓库既有 Skill 目录约定创建 `SKILL.md`、`agents/openai.yaml` 和 `resources.json`；不依赖仓库外、机器专属的初始化脚本。
2. 写入问题拆解、数据需求、假设登记和禁止提前建模规则。
3. 运行该 Skill 的契约、路由和自包含打包测试至通过；若当前 Codex 安装公开了 Skill 校验器，可附加运行，但不得把机器专属路径写入项目命令。

## Task 3：创建并验证 `data-auditor`

**Files:** `adapters/codex/skills/data-auditor/{SKILL.md,agents/openai.yaml,resources.json}`

1. 先确认测试仍因缺失目录失败。
2. 创建骨架并连接 data profile/transform 与相关基础知识。
3. 固化“原始数据只读、变换另存、失败关闭”规则。
4. 运行定向测试和快速校验。

## Task 4：创建并验证 `model-selector`

**Files:** `adapters/codex/skills/model-selector/{SKILL.md,agents/openai.yaml,resources.json}`

1. 先确认缺失失败。
2. 创建骨架，消费 33 张卡的目录、Schema 和基础知识。
3. 要求至少比较候选、基线、假设、验证和禁用场景；禁止声称运行。
4. 运行定向测试和快速校验。

## Task 5：创建并验证 `solver`

**Files:** `adapters/codex/skills/solver/{SKILL.md,agents/openai.yaml,resources.json}`

1. 先确认缺失失败。
2. 创建骨架，限定已验证能力为熵权/TOPSIS、线性回归和线性规划代表链路。
3. 不支持模型输出执行计划、缺失工具和恢复条件，不输出替代数值。
4. 运行定向测试和快速校验。

## Task 6：创建并验证 `sensitivity-analyst`

**Files:** `adapters/codex/skills/sensitivity-analyst/{SKILL.md,agents/openai.yaml,resources.json}`

1. 先添加/运行“未知参数导致零有效点”失败用例。
2. 若 Phase 2 API 仍误判稳定，以最小修复令其失败关闭。
3. 创建 Skill，要求基准、扰动范围、有效点、变化量和失效点齐全。
4. 运行定向测试和快速校验。

## Task 7：创建并验证 `literature-researcher`

**Files:** `adapters/codex/skills/literature-researcher/{SKILL.md,agents/openai.yaml,resources.json}`

1. 先确认缺失失败。
2. 创建骨架，消费检索、去重和来源评价规则。
3. 固化后端优先级、候选状态、冲突保留与无后端失败关闭。
4. 运行静态路由契约测试；部署前另由新鲜 agent 产生逐案例观测，并用 `validate_codex_route_observations.py` 验收，不用关键词脚本冒充模型行为。

## Task 8：实现确定性打包器

**Files:**

- Create: `scripts/package_codex_skills.py`
- Create: `tests/snapshots/codex-skills/test_packaging.py`

1. 先写路径越界、缺资源、哈希一致性、重复打包一致性和 `--check` 失败测试。
2. 实现复制 Skill、复制共享资源、生成排序后的 `asset-manifest.json`。
3. `--check` 使用临时目录验证源；`--check --output <dir>` 将现有发布目录与新鲜构建逐文件比对并检测漂移，均不改写目标。
4. 运行打包测试及 `python scripts/package_codex_skills.py --check`。

## Task 9：端到端建模半链路

**Files:** `tests/e2e/test_codex_modeling_flow.py`

1. 使用确定性合成数据，依次验证问题清单、模型选择、Phase 2 运行结果和有效敏感性产物所需接口。
2. 添加缺数据与不支持模型两条失败关闭场景。
3. 断言交接外壳字段和产物类型完整。

## Task 10：完整验证与交付

1. 运行六个 Phase 3 Skill 的仓库契约与打包校验；发行 catalog 同时校验 Phase 5 的第七个 Skill。
2. 运行 Phase 3 定向测试、handoff 真实索引测试和打包器 `--check`。
3. 运行完整 pytest 回归与 `git diff --check`。
4. 检查未跟踪/既有用户文件未被修改，整理使用入口和已知限制。

## 验证命令

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv run python scripts/package_codex_skills.py --check
uv run pytest tests/snapshots/codex-skills tests/e2e/test_handoff_contract.py tests/e2e/test_codex_modeling_flow.py tests/e2e/test_literature_researcher_routing.py -v -p no:cacheprovider
uv run pytest -v -p no:cacheprovider
git diff --check
```
