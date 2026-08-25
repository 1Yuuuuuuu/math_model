---
name: repro-reviewer
description: Use when five completed CUMCM modeling handoffs need an independent reproducibility and provenance audit.
---

# Repro Reviewer

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> 审查逻辑由 Python 库 `cumcm_toolkit.review.*` 承担，**不暴露为 DSH 工具**（人工门纪律）。重跑验证仅限 registry 模型，经 cumcm-tools 插件工具完成。

## Overview

Run read-only Gate 1. Verify that Phase 3 handoffs resolve to real artifacts, successful experiments, evidence links, and an environment-lock identity.

## When to Use

Use after all five modeling handoffs and their artifact, experiment, and evidence indexes exist. Rerun after any indexed record or reviewed file changes.

## Do Not Use

Do not score model quality, repair an experiment, rerun code, edit handoffs, review prose, or approve submission. This Skill must not modify reviewed material.

## Workflow

1. Normalize the five handoffs with the Python library `cumcm_toolkit.review.inputs.build_reproducibility_inputs`.
2. Reject missing records, failed experiments, missing lock hashes, broken evidence links, and unindexed outputs. 如需重跑验证：仅对 registry 模型（linear-regression / decision-tree / kmeans）用 `cumcm_model_run` + `cumcm_metrics` 复算，并与 handoff 记录比对；非 registry 方法不得重跑冒充。
3. Snapshot every reviewed file and load only `shared/rubrics/reproducibility.yaml`（`cumcm_toolkit.review.engine.load_rubric`）。
4. Run the review engine `cumcm_toolkit.review.engine.review` without a scorecard or another gate's rubric.
5. Write exactly one contract-valid（`shared/contracts/review-report.schema.json`）indexed reproducibility report（`cumcm_artifact_index`）。
6. Recheck file hashes; any change makes the report stale（`cumcm_toolkit.review.engine.is_review_current`）。

## Failure Closure

Missing or unverifiable material yields `status: blocked`, empty outputs/evidence, a failed step, and concrete resume conditions. Do not fabricate an ID, experiment result, hash, finding, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: repro-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff has one indexed report output and artifact evidence. A blocked handoff has neither.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Inputs cannot be verified |
| failed | An open S0/S1 exists |
| passed | This exact reproducibility digest passes |

## Common Mistakes

- Treating well-formed IDs as proof that records exist.
- Approving a successful run without its lock hash.
- Mixing model-quality scoring into Gate 1.
- Rerunning a non-registry method and presenting it as verification of the recorded run.
