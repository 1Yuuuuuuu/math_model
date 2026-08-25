---
name: paper-reviewer
description: Use when a CUMCM paper source and Phase 4 reports need an independent evidence-bound quality review and score.
---

# Paper Reviewer

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> 审查逻辑由 Python 库 `cumcm_toolkit.review.*` 承担，**不暴露为 DSH 工具**（人工门纪律）。

## Overview

Run read-only Gate 3. Evaluate paper quality with the seven-dimension deterministic scorecard while preserving generation and review separation.

## When to Use

Use when the paper source, evidence-resolution report, citation report, lint report, key claims, and seven scored dimensions are available.

## Do Not Use

Do not rewrite the paper, fix citations, edit LaTeX, conduct the red-team gate, audit the final submission, or approve model quality. This Skill must not modify reviewed material.

## Workflow

1. Normalize Phase 4 reports and key claims with the Python library `cumcm_toolkit.review.inputs.build_paper_inputs`.
2. Block on missing claims, invalid report states, or unverifiable evidence.
3. Snapshot paper files and load only `shared/rubrics/paper-quality.yaml`（`cumcm_toolkit.review.engine.load_rubric`）。
4. Submit all seven dimension scores with rationales and current `clm_*` evidence to `cumcm_toolkit.review.scorecard.evaluate_scorecard`.
5. Run the engine `cumcm_toolkit.review.engine.review` and write exactly one indexed paper review report（`shared/contracts/review-report.schema.json`，`cumcm_artifact_index` 登记）。
6. Recheck source hashes; revisions require a fresh report（`cumcm_toolkit.review.engine.is_review_current`）。

## Failure Closure

Missing capability, score, file, or evidence yields `status: blocked` with empty outputs/evidence and recovery instructions. Do not fabricate a citation result, score, evidence ID, finding, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: paper-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff contains one indexed report and artifact evidence; blocked output contains neither.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Review cannot be verified |
| failed | Score misses 85/70 or open S0/S1 exists |
| passed | Paper gate passes for this digest |

## Common Mistakes

- Editing prose while acting as reviewer.
- Trusting a submitted total instead of recomputing it.
- Treating paper approval as red-team or submission approval.
