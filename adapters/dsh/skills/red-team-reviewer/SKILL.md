---
name: red-team-reviewer
description: Use when every key CUMCM paper claim needs an independent judge-style challenge, boundary check, and finding report.
---

# Red Team Reviewer

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> 审查逻辑由 Python 库 `cumcm_toolkit.review.*` 承担，**不暴露为 DSH 工具**（人工门纪律）。

## Overview

Run read-only Gate 4. Challenge every key claim using its support boundary, limitations, counterexamples, stress scenarios, and alternative explanations.

## When to Use

Use after key `clm_*` claims, claim boundaries, limitations, and challenge records are available from an otherwise reviewable paper package.

## Do Not Use

Do not author missing limitations, repair claims, edit the paper, score paper style, or audit submission files. This Skill must not modify reviewed material.

## Workflow

1. Normalize key claims, boundaries, limitations, and proposed challenges（Python 库 `cumcm_toolkit.review.inputs`）。
2. Verify every key claim has a challenge record and current evidence.
3. Load only `shared/rubrics/red-team.yaml`（`cumcm_toolkit.review.engine.load_rubric`）; do not use a scorecard.
4. Record additional evidence-bound findings only with `status: open`（`shared/contracts/review-finding.schema.json`；严重度经 `cumcm_toolkit.review.severity.validate_severity` / `is_blocking` 判定）。
5. Run the engine `cumcm_toolkit.review.engine.review` and write exactly one indexed red-team report（`shared/contracts/review-report.schema.json`，`cumcm_artifact_index` 登记）。
6. Recheck reviewed file hashes and mark revisions stale（`cumcm_toolkit.review.engine.is_review_current`）。

## Failure Closure

Missing claim coverage, evidence, boundary, or capability yields `status: blocked` when review cannot execute, or a failed report when a checked rule fails. Do not fabricate a challenge outcome, evidence ID, finding, response, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: red-team-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff has one indexed report and artifact evidence. A blocked handoff has empty outputs and evidence.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Challenge cannot be verified |
| failed | An open S0/S1 remains |
| passed | Every key claim is covered for this digest |

## Common Mistakes

- Asking generic questions without claim IDs.
- Treating acknowledgement of a limitation as resolution.
- Editing the author's response during independent review.
