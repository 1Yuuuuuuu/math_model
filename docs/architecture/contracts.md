# Phase 0 契约参考

> **前置约束。** `shared/` 是开发期的唯一事实来源。所有读取或写入契约的工具，必须按对应 Schema 和 `scripts/contract_formats.py` 的 `FORMAT_CHECKER` 校验；普通消费者不能忽略自定义格式校验。尤其是时间与年度规则来源 URL，不能仅靠 JSON Schema 的默认格式处理。

本页说明十六个可交换数据对象的用途与协作边界。可用 [契约目录](../../shared/contracts/catalog.json) 找到 Schema、有效样例和无效样例；字段的精确类型、枚举和正则表达式以 Schema 为准。

## 先遵守通用表示规则

| 主题 | 必须遵守的规则 | 例子 |
| --- | --- | --- |
| 版本 | 每个对象都有 `schema_version`；除正在迁移的 `decision` 2.0 外，当前对象为 `1.0` | `"schema_version": "1.0"` |
| 标识符 | 使用小写 ASCII 前缀和 `[a-z0-9_-]`；具体前缀由对象决定 | `art_raw_data`、`exp_model_run` |
| 文件路径 | 相对工作区、使用正斜杠 `/`、不可越界；不得使用盘符、反斜杠、绝对路径、`.`/`..`/空路径段、控制字符、Windows 禁用字符 `< > : " \| ? *`、段尾点或空格，以及 `CON`、`PRN`、`AUX`、`NUL`、`COM1`–`COM9`、`LPT1`–`LPT9`、`COM¹`–`COM³`、`LPT¹`–`LPT³` 等保留设备别名（含扩展名） | `data/input.csv` 与 `docs/model card.md` 合法；`../secret.csv`、`results/NUL.txt`、`COM².log` 不合法 |
| 时间 | 所有时间都必须是带时区的 RFC 3339 字符串 | `2026-09-10T10:15:00+08:00` |
| 哈希 | SHA-256 为 64 位小写十六进制 | `aaaaaaaa...`（共 64 位） |

`scripts/contract_formats.py` 提供一致的 RFC 3339、HTTP(S) 来源 URL，以及 `cumcm-workspace-path` 可移植路径检查。`artifact.path`、`asset-manifest.assets[].source_path` 和目录内所有文件路径都使用同一个纯函数判定；Schema 仍用基础正则拦截明显危险路径，完整规则由自定义格式补齐。Codex 与 DeepSeek Harness 的等价实现必须逐字符识别 Windows 的 ASCII 数字和上标数字 `¹²³` 设备别名，不能依赖 Unicode 数字归一化或只检查 `1`–`9`。默认校验器若跳过格式检查，会放过不带时区的时间、不合规 URL 或 Windows 保留设备名。

所有 Schema 正则使用 `(?![\\s\\S])` 表示真正的字符串末尾，避免 `$` 在部分运行时把末尾换行误当成结束。目录、Schema 与 fixtures 必须是严格 JSON；`NaN`、`Infinity` 和 `-Infinity` 都会被验证器拒绝。

## 按对象处理数据

| 契约 | 用途 | 生产者 → 消费者 | ID 前缀 | 必填字段 | 失败语义 | 有效样例 |
| --- | --- | --- | --- | --- | --- | --- |
| `error` | 以稳定结构传递工具失败。 | 任意工具 → 调度器、Codex、DSH | 无独立对象 ID | `schema_version`、`code`、`message`、`recoverable`、`details` | 不符合时不能作为可处理错误传播；调用方改为记录本地校验失败。 | [error.json](../../shared/fixtures/contracts/valid/error.json) |
| `artifact` | 登记可复现的数据、代码、图表、论文等产物。 | 采集、求解、写作工具 → 实验、证据、交付流程 | `art_` | `schema_version`、`artifact_id`、`kind`、`path`、`sha256`、`created_at`、`source_artifact_ids` | 拒绝该产物，后续实验或证据不得引用它。 | [artifact.json](../../shared/fixtures/contracts/valid/artifact.json) |
| `experiment` | 记录一次可复现运行的输入、环境和输出。 | 求解工具 → 证据链、模型审查 | `exp_` | `schema_version`、`experiment_id`、`input_artifact_ids`、`code_artifact_id`、`parameters`、`random_seed`、`environment`、`started_at`、`finished_at`、`status`、`output_artifact_ids`、`metrics`；`environment` 还需 `python_version`、`lock_sha256` | 拒绝运行记录，不可据此宣称模型结果可复现。 | [experiment.json](../../shared/fixtures/contracts/valid/experiment.json) |
| `evidence-link` | 将一个主张连到产物、实验和可定位证据。 | 证据整理工具 → 审查、论文写作 | `clm_` | `schema_version`、`claim_id`、`claim_text`、`artifact_id`、`experiment_id`、`locator`、`boundary`；`locator` 还需 `kind`、`value` | 拒绝主张，审查或论文不能引用未定界的证据。 | [evidence-link.json](../../shared/fixtures/contracts/valid/evidence-link.json) |
| `decision` | 保存四道人工作关卡中的审批结果、已选择方案与理由。 | 人工评审 → 工作流、后续工具 | `dec_` | 2.0 必填 `schema_version`、`decision_id`、`gate`、`outcome`、`selected_option`、`rationale`、`artifact_ids`、`decided_by`、`decided_at`；1.0 旧对象没有 `outcome`，仅用于迁移 | 拒绝非人工决定；工作流拒绝未迁移的 1.0 决定。 | [decision.json](../../shared/fixtures/contracts/valid/decision.json) |
| `workflow-state` | 表达工作区阶段和四道关卡的当前状态。 | 工作流编排器 → 全部执行工具 | `ws_` | `schema_version`、`workspace_id`、`stage`、`gates`、`latest_artifact_ids`、`updated_at`；`gates` 还需四个 `gate_*` 字段 | 拒绝状态迁移；不能跳过前序已批准关卡进入后续阶段。 | [workflow-state.json](../../shared/fixtures/contracts/valid/workflow-state.json) |
| `review-finding` | 记录硬约束、复现、模型、论文或红队审查发现。 | 审批技能 → 修订与风险处置流程 | `finding_` | `schema_version`、`finding_id`、`review_gate`、`severity`、`summary`、`evidence_refs`、`recommendation`、`status` | 拒绝发现；没有证据引用或未定义严重性时不可据此阻断或放行。 | [review-finding.json](../../shared/fixtures/contracts/valid/review-finding.json) |
| `annual-rule` | 保存某届规则的可核验来源与可执行条目。 | 规则核验流程 → 审批、交付检查 | `cumcm-`（规则集）与 `rule_`（条目） | `schema_version`、`rule_set_id`、`year`、`source_url`、`verified_at`、`items`；每个 `items[]` 还需 `rule_id`、`description`、`enforcement`、`blocking` | 拒绝该规则集，不能以其阻断交付或宣称符合规则。 | [annual-rule.json](../../shared/fixtures/contracts/valid/annual-rule.json) |
| `asset-manifest` | 声明要交给 Codex 与 DSH 的共享资产。 | 打包流程 → Codex、DeepSeek Harness | 清单无独立对象 ID；资产为 `asset_` | `schema_version`、`manifest_version`、`assets`；每个 `assets[]` 还需 `asset_id`、`source_path`、`sha256`、`package_targets` | 拒绝清单；任一目标端不得使用未通过校验的资产。 | [asset-manifest.json](../../shared/fixtures/contracts/valid/asset-manifest.json) |
| `literature-source` | 记录可追溯的文献来源、检索与核验状态。 | 文献检索流程 → 证据整理、论文写作 | `src_` | `schema_version`、`source_id`、`title`、`authors`、`year`、`venue_or_repository`、`identifiers`、`canonical_url`、`retrieved_at`、`retrieval_backend`、`verification_status`、`artifact_ids`、`content_sha256`；已批准来源还需 `decision_id` | 拒绝来源；不能据此建立经过批准的文献证据。 | [literature-source.json](../../shared/fixtures/contracts/valid/literature-source.json) |
| `citation-link` | 将论文主张连到可定位的文献内容与支持边界。 | 证据整理工具 → 论文写作、审查 | `cite_` | `schema_version`、`citation_id`、`claim_id`、`source_id`、`usage`、`locator`、`support_boundary`、`verified_at`；`locator` 还需 `kind`、`value` | 拒绝引文；未定位或越过支持边界的主张不得引用该来源。 | [citation-link.json](../../shared/fixtures/contracts/valid/citation-link.json) |
| `modeling-handoff` | 固定建模与评审 Skill 的 complete/blocked 交接外壳。 | Codex Skill → 后续 Skill、评审流程 | 无独立对象 ID | `schema_version`、`status`、`artifact_type`、输入输出、证据与恢复字段 | 拒绝不完整 complete 或携带伪造输出的 blocked 交接。 | [modeling-handoff.json](../../shared/fixtures/contracts/valid/modeling-handoff.json) |
| `review-report` | 保存单道只读评审、评分卡、发现和输入/量表哈希。 | Reviewer Skill → 汇总器、修订流程 | `review_` | `schema_version`、评审身份、状态、scorecard、findings、errors 和哈希 | 拒绝报告；不得据此放行或进入 Phase 6。 | [review-report.json](../../shared/fixtures/contracts/valid/review-report.json) |
| `review-bundle` | 汇总五份仍为当前状态的评审报告并表达 Phase 6 readiness。 | 评审汇总器 → Phase 6 总控 | `review_bundle_` | 五个报告槽、报告摘要、readiness、阻断发现和时间 | 缺门为 blocked，过期或失败为 not_ready。 | [review-bundle.json](../../shared/fixtures/contracts/valid/review-bundle.json) |
| `workflow-event` | 记录可重放的总控事件、前序摘要、人工决定和恢复信息。 | 总控与人工门 → Codex/DSH 状态重放器 | `evt_` | 工作区、sequence、previous digest、事件类型、阶段和事件专属字段 | 断号、重排、错误决定或字段组合不合法时拒绝事件链。 | [workflow-event.json](../../shared/fixtures/contracts/valid/workflow-event.json) |
| `model-execution` | 统一模型执行成功结果与未来持久化失败记录。 | 模型执行器 → Codex、DSH、审查流程 | `model_id` 为小写连字符标识 | `schema_version`、`status`、`model_id`、`executor`、参数、输入摘要、诊断、警告、可复现性；成功时还需 `result` | 公共执行失败以异常表达；持久化 `failed` 记录不得伪造 `result`。所有数值必须有限且结果可严格 JSON 往返。 | [model-execution.json](../../shared/fixtures/contracts/valid/model-execution.json) |

## 文献契约的跨记录边界

`literature-source.canonical_url` 只有在 `retrieval_backend = user-provided` 时可以为 `null`，用于没有可伪造网络地址的离线用户文件；`paper-search` 与 `runtime-search` 记录仍必须提供通过 `cumcm-http-url` 校验的 HTTP(S) URL。

当 `artifact_ids` 有多个条目时，`content_sha256` 表示用于引用核验的主检索内容（通常是主要 PDF 或规范化全文）的 SHA-256，而不是多个 artifact 哈希的拼接或聚合值。每个附属文件继续由自己的 `artifact.sha256` 记录；未来运行时应做逐 artifact 的交叉验证，不在当前字段中压缩多个哈希。

以下约束需要解析多个记录，留给 Phase 4/6 的运行时校验：已批准来源的 `decision_id` 必须解析到 `gate = gate_3_outline` 的人工决定；每个 `citation-link.source_id` 必须解析到 `verification_status = approved` 的来源；`content_sha256` 必须与主检索 artifact 的实际哈希相符；提纲、主张、来源文件或定位修订后旧链接失效并重新核验。当前单记录 JSON Schema 不声称执行这些跨记录检查。

## 从样例开始验证

例如，要判断实验记录是否可用于论文论证，先检查它包含 `environment.lock_sha256`，再确认其时间包含时区，最后让验证器校验整个对象。不要只复制字段名称：Schema 中的枚举、最小数量和跨关卡条件同样是协议的一部分。

```powershell
uv run python scripts/validate_contracts.py
```

输出成功时，十六个已登记对象及其有效、无效样例都会被复核。无效样例只违反其文件名所表达的单一规则，因此适合在修改 Schema 后做回归检查。

## 年度规则样例的边界

[annual-rule.json](../../shared/fixtures/contracts/valid/annual-rule.json) 中的 2026 条目是 **synthetic example**，只用于验证契约；它不宣称官方规则，也绝不能作为全国大学生数学建模竞赛的实际规定。真正的年度规则更新必须走 [变更政策](../operations/change-policy.md) 的溯源核验流程。
