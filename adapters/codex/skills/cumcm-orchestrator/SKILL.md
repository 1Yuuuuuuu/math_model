---
name: cumcm-orchestrator
description: Use when a CUMCM team needs to start, resume, inspect, or advance the complete evidence-backed 72-hour workflow through its human gates.
---

# CUMCM Orchestrator

## Overview

Coordinate the complete competition workflow from intake to submission. Replay the append-only event history, derive the current state, and emit exactly one next action. The four human gates are mandatory, and this Skill must not self-approve any gate.

## When to Use

Use to start a complete CUMCM run, resume from a checkpoint, inspect overall progress, recover after failure, or determine the next cross-stage action.

## Do Not Use

Do not use for an isolated data audit, model run, paper review, or submission audit when no full-workflow coordination is requested. Do not replace a specialist Skill, invent a missing paper-writing capability, or treat the optional literature branch as a fifth gate.

## Workflow

Before acting, read `resources.json`. In a packaged Skill, resolve every resource under `references/<source path>`.

1. Validate and replay all `workflow-event` records in append order. Treat replayed state, not conversation memory, as authoritative.
2. Validate referenced human `decision` records and any attached `review-bundle`. A decision must be human-authored and match the exact gate and artifacts.
3. Call the deterministic next-action policy and present exactly one action. Never launch two child Skills in the same orchestration step.
4. For `child_skill`, invoke only the named catalog Skill in configured order. Index its real outputs, then append `child_completed`; never infer completion from prose or append `stage_completed` early.
5. For `stage_work`, use the named capability only when it is actually available. Otherwise return a blocked handoff identifying the missing capability.
6. For `human_gate`, stop and request the human decision. Append `gate_decided` only after a valid decision record exists.
7. For `recovery`, preserve all prior artifacts and follow `resume_when`; append `resumed` only after the condition is satisfied.
8. Keep literature retrieval optional. Record `required` or `skipped`; when required, route to `literature-researcher` and carry verified candidates into Gate 3 evidence.
9. Before Gate 4, run all five independent reviewers, build a current ready review bundle whose `reviewed_artifact_ids` identify the current paper/PDF, attach those same IDs, then stop for a human decision bound to the same artifacts.
10. Persist the latest event history and derived checkpoint after every accepted event.

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
