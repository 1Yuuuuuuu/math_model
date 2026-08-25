# 使用五道独立评审门

Phase 5 已提供五个彼此隔离的只读入口。生成与评审隔离：Reviewer 只能读取输入、形成报告，不能修改模型、实验、论文、LaTeX 或 PDF。

| 门 | Skill | 负责内容 |
| --- | --- | --- |
| Gate 0 | `submission-auditor` | 构建、lint、引用、PDF、哈希与年度规则 |
| Gate 1 | `repro-reviewer` | 五份建模交接、产物/实验/证据索引和锁文件 |
| Gate 2 | `model-reviewer` | 模型规则与六维评分卡 |
| Gate 3 | `paper-reviewer` | 证据、引用、lint 与七维论文评分卡 |
| Gate 4 | `red-team-reviewer` | 核心主张覆盖、边界、局限与评委质询 |

不要用一个 Reviewer 代跑另一道门。每个完整 Skill 输出一份正式 `review-report`；执行失败时输出 `status: blocked` 外壳，不携带伪造报告。

## 推荐运行顺序

在 Codex 中依次调用：

```text
使用 $submission-auditor 审计最终源文件和 PDF。
使用 $repro-reviewer 核验五份 Phase 3 交接及其索引。
使用 $model-reviewer 独立评审模型并填写六维证据评分。
使用 $paper-reviewer 独立评审论文并填写七维证据评分。
使用 $red-team-reviewer 对每个核心 clm_* 主张形成质询。
```

模型与论文评分由工具重新计算，内部通过线为加权总分至少 85，且每个维度至少 70。它们不是官方权重；任何 open S0/S1 都优先导致 `failed`，不能被高分覆盖。

## 状态解释

| 状态 | 含义 | 恢复方式 |
| --- | --- | --- |
| `blocked` | 缺文件、证据、能力或可验证材料 | 按 errors 和 resume_when 补齐后重跑 |
| `failed` | open S0/S1 或评分未达 85/70 | 在 Reviewer 之外修订，保存新产物后重跑 |
| `passed` | 当前输入、量表和文件哈希通过 | 保存报告并进入汇总 |

S2/S3 不阻断，但会保留。不得原地修改旧报告或把 finding 标记为已解决；修订后重新评审。

## 旧报告失效

报告绑定输入、量表、评分材料、外部 findings 与被审文件 SHA-256。任何一项变化都会使报告 stale。论文源文件变化至少使论文、红队和提交三门失效；若结论或数值也变化，还应重跑模型和复现门。

## 汇总到 Phase 6

`build_review_bundle` 会重新运行并比对五份报告。调用时必须同时提供 `reviewed_artifact_ids`，将评审包绑定到当前论文/PDF artifact；这些 ID 参与 `bundle_id` 的确定性计算。缺门或缺评分材料为 `blocked`；报告过期或单门失败为 `not_ready`；只有五门均通过且仍为当前状态时才是 `ready_for_phase_6`。

当前正式目录为 15 项合同，Codex 发行目录为 12 个 Skill。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/review tests/e2e/test_five_gate_review_flow.py -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
```

预期合同验证为 15 项零错误，打包检查为 `{"skills": 12, "status": "ok"}`。仓库内快照验证不替代部署环境中的真实 Agent 前向观测。
