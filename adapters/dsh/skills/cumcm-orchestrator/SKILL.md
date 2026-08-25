---
name: cumcm-orchestrator
description: Use when a CUMCM team needs to start, resume, inspect, or advance the complete evidence-backed 72-hour workflow through its human gates.
---

# CUMCM Orchestrator

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> workflow 状态机逻辑由 Python 库 `cumcm_toolkit.workflow.*` 承担，**不暴露为 DSH 工具**；本 Skill 编排 12 个 catalog Skill（名字与 Codex catalog 一致）。

## Overview

Coordinate the complete competition workflow from intake to submission. Replay the append-only event history, derive the current state, and emit exactly one next action. The four human gates are mandatory, and this Skill must not self-approve any gate.

## When to Use

Use to start a complete CUMCM run, resume from a checkpoint, inspect overall progress, recover after failure, or determine the next cross-stage action.

## Do Not Use

Do not use for an isolated data audit, model run, paper review, or submission audit when no full-workflow coordination is requested. Do not replace a specialist Skill, invent a missing paper-writing capability, or treat the optional literature branch as a fifth gate.

## Workflow

1. Validate and replay all `workflow-event` records in append order with the Python library `cumcm_toolkit.workflow.events.validate_event_chain` + `cumcm_toolkit.workflow.state.replay_workflow`. Treat replayed state, not conversation memory, as authoritative（契约：`shared/contracts/workflow-event.schema.json`）。
2. Validate referenced human `decision` records（`shared/contracts/decision.schema.json`）and any attached `review-bundle`（`shared/contracts/review-bundle.schema.json`）via `cumcm_toolkit.workflow.gates.validate_gate_decision` / `index_decisions` / `index_review_bundles`. A decision must be human-authored and match the exact gate and artifacts.
3. Call the deterministic next-action policy `cumcm_toolkit.workflow.actions.next_action` and present exactly one action. Never launch two child Skills in the same orchestration step.
4. For `child_skill`, invoke only the named catalog Skill（12 个名字与 Codex catalog 一致）。Index its real outputs with `cumcm_artifact_index`, then append `child_completed`（`cumcm_toolkit.workflow.events.create_event`）; never infer completion from prose or append `stage_completed` early.
5. For `stage_work`, use the named capability only when it is actually available（DSH 侧能力面见各 Skill：registry 模型、literature 门禁等）。Otherwise return a blocked handoff identifying the missing capability.
6. For `human_gate`, stop and request the human decision. Append `gate_decided` only after a valid decision record exists.
7. For `recovery`, preserve all prior artifacts and follow `resume_when`; append `resumed` only after the condition is satisfied.
8. Keep literature retrieval optional. Record `required` or `skipped`; when required, route to `literature-researcher` and carry verified candidates into Gate 3 evidence（`literature_search` 无后端/未授权时 blocked，按文献 Skill 的 Failure Closure 处理）。
9. Before Gate 4, run all five independent reviewers, build a current ready review bundle（`cumcm_toolkit.review.bundle.build_review_bundle`）whose `reviewed_artifact_ids` identify the current paper/PDF, attach those same IDs, then stop for a human decision bound to the same artifacts.
10. Persist the latest event history and derived checkpoint after every accepted event（`cumcm_toolkit.workflow.persistence.save_workflow_checkpoint`）。

## Failure Closure

Invalid event chains, unresolved records, stale review bundles, unavailable capabilities, specialist failure, or missing human decisions produce `status: blocked`. Populate `missing_inputs`, `failed_step`, and actionable `resume_when`. Do not fabricate outputs, evidence, event IDs, approvals, review results, literature, metrics, or completion.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: workflow-checkpoint
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
next_action: {}
```

A complete handoff indexes the append-only history and derived checkpoint, preserves their hashes, and contains exactly one deterministic `next_action`. A blocked handoff carries no claimed output or evidence.

## Quick Reference

| Runtime state | Only allowed response |
| --- | --- |
| `running` | One specialist, stage-work, bundle, or packaging action |
| `waiting_human` | Stop at the named gate |
| `blocked` | One recovery action with `resume_when` |
| `complete` | Report completion; run nothing else |

## Common Mistakes

- Advancing from remembered chat state instead of replaying events.
- Running several specialist Skills before recording each completion.
- Treating an assistant statement as a human gate decision.
- Reusing a review bundle after any reviewed artifact changes.
- Claiming outline or paper writing exists when the capability is unavailable.
