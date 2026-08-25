# Phase 3 Codex 建模 Skills 设计

**状态：** 已确认，可直接实施
**范围：** Codex 建模半链路，不包含论文正文生成、引用批准或总编排器

## 目标

交付六个可独立触发、可组合、失败关闭的 Phase 3 Codex Skills，使 Codex 能从赛题拆解推进到数据审计、模型选择、已验证模型求解、敏感性分析和候选文献研究，并让每一步都有稳定的输入输出约定与真实证据来源。发行 catalog 当前另含 Phase 5 的 `model-reviewer`，因此打包总数为 7，但不把它计入 Phase 3 的六个建模 Skill。

## 设计原则

1. `shared/` 是知识、模型卡和文献规则的唯一事实来源；Skill 源码不复制这些内容。
2. 六个 Skill 独立工作，Phase 3 不增加总编排 Skill；统一编排留给 Phase 6。
3. 缺少输入、工具或有效实验时返回阻塞信息，不补造数值、文献或“稳定”结论。
4. `solver` 只执行 Phase 2 已验证的评价、预测、优化代表能力；其余模型卡只形成执行计划和缺失工具清单。
5. `literature-researcher` 只生成候选记录；正式引用批准、BibTeX 和论文引用进入 Phase 4。
6. 源目录便于维护，打包产物自包含；每个复制资源都记录来源路径和 SHA-256。

## Skill 边界

| Skill | 触发条件 | 主要产物 | 明确不做 |
| --- | --- | --- | --- |
| `problem-reader` | 收到赛题、附件说明或需要拆题 | 问题清单、目标、约束、数据需求、假设登记 | 不选择最终模型，不生成结果 |
| `data-auditor` | 已有数据，需要质量检查或可重复清洗 | 数据画像、风险、变换计划、变换后证据 | 不静默覆盖原始数据 |
| `model-selector` | 问题与数据特征已知，需要比较候选模型 | 候选比较、入选理由、基线和验证计划 | 不声称模型已运行 |
| `solver` | 模型已选且输入完备，需要实际求解 | 运行记录、参数、指标、产物索引或阻塞说明 | 不为不支持模型伪造结果 |
| `sensitivity-analyst` | 已有可复现实验，需要稳健性/敏感性分析 | 扰动设计、有效点、变化量、结论与失效点 | 无有效扰动点时不判定稳定 |
| `literature-researcher` | 需要检索模型依据、方法来源或相关研究 | 检索式、后端选择、候选文献及待核验项 | 不批准引用，不生成正式 BibTeX |

## 结构化交接

每个 Skill 的最终交接使用同一外壳：

```yaml
status: complete | blocked
artifact_type: problem-analysis | data-audit | model-selection | solver-run | sensitivity-report | literature-candidates
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

`complete` 必须有可检查的输出；`blocked` 必须填写 `missing_inputs` 或 `failed_step`，并保持 `outputs` 为空或只包含诊断产物。

## 资源与打包

每个 Skill 源目录包含：

- `SKILL.md`：触发、边界、工作流、失败关闭和交接格式。
- `agents/openai.yaml`：Codex UI 元数据和默认提示。
- `resources.json`：该 Skill 消费的仓库资源清单。

`scripts/package_codex_skills.py` 将每个 Skill 复制到目标目录，把 `resources.json` 中的资源放入 `references/<source path>`，并生成 `asset-manifest.json`，避免 `shared/shared` 双重前缀。`--check` 在临时目录校验源；`--check --output <dir>` 还会逐文件比较已生成目录，发现缺失、多余或内容漂移即失败。

## 路由规则

路由快照为每个 Skill 保存触发与不触发样例。静态测试要求描述只陈述“何时使用”，正文包含“不适用”边界。该快照只定义测试用例，不等同于真实 LLM 路由行为通过；部署前必须在可启动独立 agent 的环境逐条运行，并用 `scripts/validate_codex_route_observations.py` 校验每个案例唯一的真实观测记录。验收器拒绝缺失、重复、错误 trigger 和错误 non-trigger；它不生成观测，也不得用关键词分类代替 agent 前向运行。跨 Skill 请求可以依次使用多个 Skill，但单个 Skill 不越权替下游步骤给结论。

文献后端按以下顺序选择：当前运行时已批准的检索工具、已安装且可调用的论文检索 Skill、用户提供的 DOI/PDF/URL/元数据。若都不可用，只输出检索计划并返回 `blocked`；不得补全作者、题名、DOI 或结论。

## 验收

1. 六个 Phase 3 Skill 通过格式、发现描述、边界和真实交接契约测试；发行 catalog 的 7 个 Skill 全部通过自包含打包检查。
2. 每个 Skill 至少有一个触发和一个不触发快照；这属于静态覆盖，不冒充 agent 行为评测。
3. 缺数据、缺工具、无有效敏感性点和无文献后端均失败关闭。
4. 合成建模场景可形成问题分析、模型选择、实验结果和敏感性产物。
5. 打包器 `--check` 通过，重复打包内容哈希一致，资源哈希与 `shared/` 一致。
6. 独立 agent 前向评测在具备相应运行授权时执行；未执行前不得声称自然语言路由已经验证。

## 延后项

- 论文提纲、正文、BibTeX、LaTeX/PDF：Phase 4。
- 全流程编排和人工门：Phase 6。
- DSH 适配器：由 DSH 负责的相应阶段消费相同 `shared/` 契约，不在 Codex Skill 中复制实现。
