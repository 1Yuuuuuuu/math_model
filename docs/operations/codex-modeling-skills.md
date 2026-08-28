# 使用 Codex 建模 Skills

工作台当前提供 Phase 3 的六个建模 Skill，以及 Phase 5 的独立 `model-reviewer`，用于把国赛赛题推进到可追溯的建模结果、候选文献和模型审批；它们不会自动生成论文正文，也不会批准正式引用。

> 重要：缺少赛题、数据、已验证工具或有效实验点时，Skill 会返回 `blocked`。这是证据保护机制，不应通过要求“先给一个大概结果”绕过。

## 快速开始

在 Codex 中按当前任务显式调用对应 Skill。首次完整建模建议依次使用：

```text
使用 $problem-reader 拆解这道国赛题，列出子问题、数据需求、约束和待确认假设。
使用 $data-auditor 审计附件数据，原始文件保持只读，并生成可重复的变换计划。
使用 $model-selector 根据问题分析和数据审计比较候选模型、基线与验证方案。
使用 $solver 执行已选且受支持的模型，记录参数、种子、指标和产物证据。
使用 $sensitivity-analyst 对已固化实验进行有依据的参数扰动与稳定性分析。
使用 $literature-researcher 为指定主张检索候选来源，只保留待核验记录。
使用 $model-reviewer 只读评审五类建模交接物，记录严重度、问题和输入哈希。
```

不必每次使用全部六个 Phase 3 建模 Skill。发行目录中的第七个 `model-reviewer` 属 Phase 5。例如已有合格实验时，可以直接调用 `sensitivity-analyst`；只有赛题没有数据时，应停在 `problem-reader` 的数据需求清单。

## 选择正确的 Skill

| 你现在要做的事 | 使用 | 必要输入 | 成功产物 |
| --- | --- | --- | --- |
| 拆题、澄清目标 | `$problem-reader` | 赛题正文和附件说明 | `problem-analysis` |
| 检查和清洗数据 | `$data-auditor` | 数据文件、字段含义 | `data-audit` |
| 比较模型 | `$model-selector` | 问题分析、数据审计 | `model-selection` |
| 运行模型 | `$solver` | 完整模型选择、数据、指标 | `solver-run` |
| 检验稳健性 | `$sensitivity-analyst` | 可复现实验、参数和评价函数 | `sensitivity-report` |
| 查找论文依据 | `$literature-researcher` | 待支持主张、检索边界 | `literature-candidates` |

`$solver` 不维护手写白名单：它查询 `cumcm_toolkit.models.specifications.list_capabilities()`，只有注册表中的能力才会进入执行。当前 26 项能力及逐项最小 payload、核心输出和失败示例见 [模型执行器运行手册](model-executors.md)；其他模型卡只用于选择和设计，执行时返回计划、缺失工具和恢复条件，不产生替代数值。

公开执行边界固定为 `cumcm_toolkit.models.execution.execute(model_id, payload)`：这是 Codex/DSH 使用的 JSON 结果契约。`run_model(name, X, y)` 是 legacy Python 兼容入口，会返回 fitted estimator，只供旧调用方使用，不能放进 Skill 或 DSH 交接。

## 处理交接结果

所有 Skill 使用相同外壳。先检查 `status`：

```yaml
status: blocked
artifact_type: solver-run
inputs: []
outputs: []
evidence: []
missing_inputs:
  - verified ARIMA runner
failed_step: capability check
resume_when:
  - install and verify the required runner
```

- `complete`：检查 `outputs` 和 `evidence` 后再进入下一步。
- `blocked`：根据 `missing_inputs`、`failed_step` 和 `resume_when` 补齐条件，然后重新运行当前 Skill。
- 阻塞结果中的诊断不等于模型结果；不得进入论文数值或结论。

## 使用文献研究

`$literature-researcher` 的后端顺序固定为：当前运行时已批准的搜索工具、已安装且可调用的论文检索 Skill、用户提供的 DOI/PDF/URL/元数据。

推荐请求写法：

```text
使用 $literature-researcher 查找“熵权法用于多指标评价时对样本差异的依赖”相关候选来源。
拟支持主张：权重会受样本离散程度影响。
范围：中英文均可，优先方法论文和可核验全文；不要批准引用或生成正式 BibTeX。
```

如果没有任何后端，Skill 只返回检索问题、关键词和过滤条件，并标记 `blocked`。候选文献进入论文前仍需后续证据审查和人工批准。

## 打包与检查

日常修改后先运行只读检查：

```powershell
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
```

需要给 Codex 或其他兼容 Agent Skills 的运行环境加载时，打包到一个不存在的空目录：

```powershell
.venv\Scripts\python.exe scripts/package_codex_skills.py --output dist/codex-skills
.venv\Scripts\python.exe scripts/package_codex_skills.py --check --output dist/codex-skills
```

输出中的每个 Skill 都含 `SKILL.md`、`agents/openai.yaml`、资源声明、自包含的 `references/<source path>` 和 `asset-manifest.json`。清单中的 SHA-256 用于确认打包资源与仓库 `adapters/`、`shared/`、`toolkit/` 来源一致；第二条命令会拒绝发布目录中的缺失、多余或被修改文件。

Skill 清单由 `adapters/codex/skills/catalog.json` 统一维护；实际打包要求目标目录不存在，并通过临时目录完成后一次性替换，避免覆盖旧包或留下半成品。

DeepSeek Harness 适配层应消费同一份共享资源和交接字段；不要把 Codex 打包产物反向复制成第二套知识源。

路由快照测试只定义触发/不触发案例，不能单独证明真实模型行为。部署前必须让新鲜、互相隔离的 agent 逐条运行 `tests/snapshots/codex-skills/routing-cases.yaml`，把实际选择保存为 JSON 数组；每条记录至少包含 `run_id`、`model`、`skill`、`case_type`、`prompt` 和 `observed_skill`。不得用关键词脚本生成或补写观测结果。

完成真实前向运行后执行：

```powershell
.venv\Scripts\python.exe scripts/validate_codex_route_observations.py --observations routing-observations.json
```

验收器要求 48 个案例各有且只有一条观测：trigger 必须选择目标 Skill，non-trigger 不得选择被禁止的目标 Skill；缺失、重复或错误路由都会失败。仓库测试只验证该验收器本身，未提供真实 `routing-observations.json` 时不得声称自然语言路由已经通过。

## 修改后的验证

```powershell
.venv\Scripts\python.exe -m pytest tests/snapshots/codex-skills tests/e2e/test_handoff_contract.py tests/e2e/test_codex_modeling_flow.py tests/e2e/test_literature_researcher_routing.py -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
```

预期结果为相关测试全部通过，打包检查输出 `{"skills": 12, "status": "ok"}`。
