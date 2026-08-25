# Phase 6 确定性总控与恢复闭环设计

**日期：** 2026-08-25
**状态：** ✅ 已完成并通过全库验证
**依赖：** Phase 1–5 已完成；Phase 5 `review-bundle` 为最终评审稳定输入

## 目标

交付一个只负责编排、不替代子 Skill 推理的 `cumcm-orchestrator`。总控以 append-only 事件日志驱动已有 `workflow-state` 快照，强制四个人工确认门，支持失败后从最近有效检查点恢复，并在需要外部文献证据时才启动可选文献分支。

Phase 6 完成后，同一事件序列在 Codex 与未来 DSH 适配中必须得到相同状态；未确认人工门、过期评审、失败子任务或无效事件都不能被提示词绕过。

## 方案裁决

采用“事件日志为事实、状态快照为派生结果”的方案：

- `workflow-event` 是新增正式合同，记录顺序、前序摘要、事件类型、阶段、人工决定、产物和恢复信息。
- `workflow-state` 保持现有 1.0 合同，不增加运行时私有字段，作为每次重放后的兼容快照。
- `decision` 继续保存人类选择、理由和产物版本；事件中的 `outcome` 决定批准或拒绝，`decision_id` 必须解析到同一 gate 的 human decision。
- `review-bundle` 是 Gate 4 的必要输入；只有 `ready_for_phase_6` 的当前汇总才能允许 Gate 4 批准。
- `cumcm-orchestrator` 只选择下一动作、调用一个子 Skill、记录结果和停在人工门，不生成模型数值、不写论文、不替 Reviewer 修订。

不采用可变单文件状态或纯提示词编排：前者无法提供完整历史，后者无法确定性重放或供 DSH 做一致性测试。

## 状态和阶段

沿用现有阶段：

```text
intake → model_design → solve → outline → write → review → submission → complete
```

四个人工门的唯一合法推进点：

| 人工门 | 当前阶段 | 批准后阶段 | 必须绑定的产物 |
| --- | --- | --- | --- |
| `gate_1_problem` | `intake` | `model_design` | 问题拆解和数据需求 artifact |
| `gate_2_model` | `model_design` | `solve` | 候选模型、主模型、基线和实验设计 artifact |
| `gate_3_outline` | `outline` | `write` | 论文提纲、引用清单及可选候选文献 artifact |
| `gate_4_submission` | `review` | `submission` | 当前 `review-bundle` 与最终论文/PDF artifact |

自动阶段推进只发生在已固化事件上：`solve` 完成后进入 `outline`；`write` 完成后进入 `review`；Gate 4 批准后进入 `submission`；提交包固化后进入 `complete`。任何门 rejected 时阶段保持不变，状态返回 blocked，并记录恢复条件。

## workflow-event 合同

合同目录从 14 增加到 15。每条事件包含：

```yaml
schema_version: "1.0"
event_id: evt_<16 hex>
workspace_id: ws_...
sequence: 0
previous_event_digest: null
event_type: workspace_started | child_completed | stage_completed | stage_failed | resumed | gate_decided | literature_branch_decided | review_bundle_attached | submission_completed
stage: intake
skill: null
gate: null
decision_id: null
outcome: null
artifact_ids: []
review_bundle_id: null
literature_required: null
failure_code: null
resume_when: []
occurred_at: <RFC3339>
```

事件 ID 由不含 `event_id` 的规范事件材料计算。`sequence` 从 0 连续递增；除首事件外，`previous_event_digest` 必须等于前一完整事件的 SHA-256，时间戳不得倒退。每种事件的无关字段必须保持 null/空数组。任何断号、重排、重复 ID、错误摘要、未来阶段事件或字段组合不合法都拒绝整条日志。

条件约束：

- `workspace_started` 只能是 sequence 0、stage `intake`。
- `child_completed` 必须提供一个已登记 Skill 名和至少一个真实 artifact，用于确定性选择同阶段的下一个子 Skill。
- `stage_completed` 必须提供产物；只有当前阶段且配置要求的子 Skill 已按顺序完成时才允许完成。
- `stage_failed` 必须有 failure code 与恢复条件，不改变阶段或已有产物。
- `resumed` 只能紧跟可恢复失败，清除运行阻塞但不删除历史。
- `gate_decided` 必须提供 gate、decision ID、approved/rejected outcome；批准前核验真实 decision 及产物集合。
- `literature_branch_decided` 只允许在 `solve|outline`，明确 required/skipped；required 时必须在 Gate 3 前形成候选文献 artifact。
- `review_bundle_attached` 只允许在 `review`，必须由当前文件、量表、评分和报告现场调用 `build_review_bundle` 后产生，解析到完整且 current 的 Phase 5 汇总；不能只信任磁盘上的旧 readiness 字段。
- `submission_completed` 只允许 Gate 4 已批准后的 `submission`，必须提供最终提交 artifact。

## 决定和人工门

总控不能创建 `decision` 并自称人类。它只消费外部提供且通过合同的记录，并执行跨记录校验：

- `decided_by` 必须是 `human`。
- decision gate 与 event gate 一致。
- decision 的 artifact IDs 非空且全部存在于当前已固化 artifact 集合。
- 一个 gate 在当前修订上只能有一个生效批准；新修订使依赖该修订的后续 gate 与评审失效。
- Gate 4 approved 还要求已 attached bundle 为 `ready_for_phase_6`，报告仍 current，`reviewed_artifact_ids` 参与 bundle 身份计算，且 bundle、attach 事件与决定绑定同一最终论文/PDF artifact。总控在追加 attach 事件前负责用 Phase 5 builder 重验；attach 后若出现任何新 artifact/revision 事件，已附 bundle 立即失效并必须重建。

## 可选文献分支

是否需要文献不是第五个人工门。总控根据显式 `literature_required` 事件选择：

- skipped：直接进入提纲准备。
- required：调用 `literature-researcher` 产生候选记录；候选不能自动 approved，也不能直接进入正式引用。
- 候选文献、拟支持主张和引用清单随提纲在 Gate 3 一并由人类确认。

缺检索能力时分支 blocked，但主流程保留检查点；用户提供合法候选材料后可 resume。

## 失败、恢复和幂等

每次子 Skill 失败记录 `stage_failed`，不覆盖已存在 artifact，不推进阶段。`resume_when` 必须具体说明缺输入或恢复动作。满足条件后追加 `resumed`，再执行当前阶段；不得删除失败事件。

事件追加和重放是幂等的：相同规范事件材料产生相同 ID；重复追加同一事件返回已有状态，事件 ID 相同但内容不同则拒绝。恢复只从最新完整事件链重放，不扫描目录猜测阶段。

## 确定性工具接口

```python
def create_event(..., history: Iterable[Mapping[str, object]]) -> dict[str, object]: ...

def replay_workflow(
    events: Iterable[Mapping[str, object]],
    *,
    decisions: Iterable[Mapping[str, object]] = (),
    review_bundles: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Return {state, runtime_status, blocked_reason, resume_when, literature_branch, review_bundle_id, last_event_digest}."""

def next_action(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Return one deterministic child-Skill action, human gate request, recovery action, or completion."""
```

所有函数为纯逻辑或显式 append helper；不自动运行子 Skill，不直接写论文或修改已固化产物。

## 工作流配置

`shared/workflows/stage-transitions.yaml` 固定事件/阶段/门转移，`cumcm-72h.yaml` 只提供建议时间盒、子 Skill 路由和必备产物，不让时间到期自动批准或跳过门。代码验证配置 ID、阶段顺序和已登记 Skill，禁止任意表达式或动态导入。

建议路由：

- intake：`problem-reader`、`data-auditor`
- model_design：`model-selector`
- solve：`solver`、`sensitivity-analyst`，按需 `literature-researcher`
- outline/write：调用已有 Phase 4 确定性论文能力；Phase 6 不新建第二套论文生成器
- review：五个 Phase 5 Reviewer 与 `build_review_bundle`
- submission：`submission-auditor` 已在 review 中完成硬门，Phase 6 只固化最终包

## cumcm-orchestrator Skill

发行目录从 11 增加到 12。Skill 必须：

- 在用户要求完整竞赛流程、继续/恢复现有比赛工作区或查看下一步时触发。
- 在单点数据审计、选模、求解、论文评审或一般知识学习时不触发。
- 每轮最多选择一个确定性下一动作；人工门返回请求而不是继续执行。
- 使用正式合同与工作流配置，不从聊天记忆推断已批准状态。
- 子 Skill blocked/failed 时记录事件并停止；不得伪造其输出。

## 测试策略

1. 合同：workflow-event 正负 fixtures、严格正则、目录 15 项。
2. 事件：确定性 ID、连续 sequence、摘要链、字段条件、重复幂等和篡改拒绝。
3. 状态机：所有合法转移、四门不可跳过、rejected 保持阶段、Gate 4 review bundle 前置。
4. 恢复：失败不覆盖产物，resume 后从同阶段继续，重放结果稳定。
5. 文献分支：required 才路由 researcher，候选随 Gate 3，不产生第五门。
6. Skill：12 个目录、触发/非触发、资源闭包、打包与格式验证。
7. E2E：从 intake 到 complete；每个人工门前停住；评审 stale 时 Gate 4 不能批准。
8. 全仓：pytest、合同验证、Skill 打包、差异格式和真实 Agent 前向观测部署门说明。

## 完成标准

- workflow-event 成为第 15 项正式合同，事件链可确定性验证和重放。
- 四个人工门没有任何自动或提示词绕过路径。
- Phase 5 bundle 过期、失败或缺失时 Gate 4 无法批准。
- 失败恢复不覆盖已固化产物，重复重放产生相同快照。
- 可选文献分支不增加第五人工门。
- `cumcm-orchestrator` 可自包含打包，发行目录为 12 个 Skill。
- 完整流程、恢复、文献分支、全仓和合同验证全部通过。

达到以上标准后，Phase 7 只需要适配 workflow-event、workflow-state、decision 和 review-bundle，不复制 Codex 提示词状态机。

## 非目标

- 自动替人批准四道门。
- 在 Phase 6 实现 DSH 插件或双端打包器。
- 用 72 小时时间盒强制跳过质量门。
- 自动修订失败模型、论文或 finding。
- 替代现有 Phase 3–5 独立 Skill 和确定性工具。
