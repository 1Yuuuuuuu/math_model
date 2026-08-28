---
name: model-reviewer
description: Use when a normalized CUMCM model package needs an independent quality score and model-only approval review.
---

# Model Reviewer

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> 审查逻辑由 Python 库 `cumcm_toolkit.review.*` 承担，**不暴露为 DSH 工具**（人工门纪律）：本 Skill 只消费库与契约，不注册/调用任何 review 工具。

## Overview

Perform the read-only Gate 2 model-quality review. This Skill cannot approve reproducibility, paper, red-team, or submission gates; a separate reproducibility review is always required.

## When to Use

Use after normalized model-selection, validation, baseline, solver, and sensitivity evidence plus all six model score dimensions exist. Use again after any reviewed input, rubric, or file changes.

## Do Not Use

Do not use to run the reproducibility rubric, select a replacement model, tune parameters, edit code, rerun experiments, review the paper, conduct red-team questioning, or approve submission. This Skill must not modify any reviewed input.

## Workflow

1. Require normalized model inputs with real `clm_*` evidence and all six score dimensions. Missing or unverifiable inputs produce a blocked report. Normalization uses the Python library `cumcm_toolkit.review.inputs.build_model_inputs`.
2. Snapshot or hash every reviewed input before review.
3. Load only the rubric `shared/rubrics/model-quality.yaml`（经 `cumcm_toolkit.review.engine.load_rubric`）；do not load reproducibility, paper, red-team, or submission rules.
4. Submit dimension scores, rationales, and current evidence to the deterministic scorecard `cumcm_toolkit.review.scorecard.evaluate_scorecard`, then run the model gate once via `cumcm_toolkit.review.engine.review`.
5. Report every finding（`shared/contracts/review-finding.schema.json` 形状）with evidence location, S0–S3 severity（`cumcm_toolkit.review.severity.validate_severity` / `is_blocking`）, summary, and revision recommendation; emit one contract-valid report per `shared/contracts/review-report.schema.json`.
6. Recheck input hashes after review; they must match the pre-review snapshot.
7. Preserve the report and its `input_digest`. Any subsequent input change requires a new review（`cumcm_toolkit.review.engine.is_review_current`）。Index the report with `cumcm_artifact_index`.

## Failure Closure

Missing handoffs, missing or invalid evidence references, invalid rubrics, or changed source hashes produce `status: blocked`. Populate `missing_inputs`, `failed_step`, and `resume_when`. Do not fabricate a finding evidence ID, approval, repaired model, metric, experiment, or review result.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: model-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

`status` describes whether the review workflow executed; `decision_status` is the approval result. A complete output contains one indexed model review report, its scorecard, evaluated rule IDs, findings, source hashes, `input_digest`, `rubric_digest`, and an explicit current/stale result.

## Quick Reference

| Decision status | Meaning |
| --- | --- |
| `blocked` | Review could not run; no approval |
| `failed` | At least one open S0/S1 finding |
| `passed` | No open S0/S1 finding for this digest |
| stale digest | Inputs changed; rerun review |

## Common Mistakes

- Editing the model while acting as reviewer.
- Treating S2/S3 as absent because they do not block.
- Reusing a report after any reviewed input changes.
- Mixing paper-quality findings into the model gate.
