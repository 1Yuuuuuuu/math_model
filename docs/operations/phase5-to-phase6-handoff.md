# Phase 5 → Phase 6 使用说明

Phase 6 的稳定输入只有五门评审汇总。生成与评审隔离；Phase 6 不应跳过某门、重写单门报告或从散落文件猜测审批结论。

## 固定接口

- 正式合同：`shared/contracts/review-bundle.schema.json`
- 汇总函数：`cumcm_toolkit.review.bundle.build_review_bundle`
- 固定槽位：`submission`、`reproducibility`、`model`、`paper`、`red_team`
- 固定量表：`submission`、`reproducibility`、`model-quality`、`paper-quality`、`red-team`
- 固定入口：`submission-auditor`、`repro-reviewer`、`model-reviewer`、`paper-reviewer`、`red-team-reviewer`

汇总调用必须提供五份报告、每门当前输入、当前量表、每门被审文件、共同文件根目录、`reviewed_artifact_ids`，以及模型/论文的当前评分维度。存在独立 Reviewer findings 时，也必须提供生成报告时的原始 finding 材料，才能重建报告。

## Phase 6 判定

1. `readiness: blocked`：缺门、错量表、Schema 无效、缺评分材料或无法重验。总控停在恢复状态。
2. `readiness: not_ready`：报告过期、某门 `failed|blocked` 或存在 open S0/S1。总控回到对应修订环节。
3. `readiness: ready_for_phase_6`：五门均 `passed`、仍为 current、无 open S0/S1。此状态只允许进入 Phase 6 设计的下一人工确认点，不代表最终提交。

## 修订恢复

- 先在 Reviewer 之外修改并固化新 artifact。
- 重跑受影响的单门 Skill，保留旧报告作为历史记录。
- 用全部当前报告重新调用 `build_review_bundle`。
- 确认 `reviewed_artifact_ids` 指向当前论文/PDF；Gate 4 决定必须绑定同一组 artifact。
- 不修改旧 `review_id`、哈希或 finding 状态来伪造 current。

当前发布基线包含 15 项正式合同和 12 个可打包 Codex Skill（含 Phase 6 总控）。真实 Agent 前向观测仍是部署门：仓库静态路由案例通过，不等于目标 Codex/DSH 运行时已经观察到相同触发行为。
