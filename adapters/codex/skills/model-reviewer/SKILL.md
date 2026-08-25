---
name: model-reviewer
description: Use when a normalized CUMCM model package needs an independent quality score and model-only approval review.
---

# Model Reviewer

## Overview

Perform the read-only Gate 2 model-quality review. This Skill cannot approve reproducibility, paper, red-team, or submission gates; a separate reproducibility review is always required.

## When to Use

Use after normalized model-selection, validation, baseline, solver, and sensitivity evidence plus all six model score dimensions exist. Use again after any reviewed input, rubric, or file changes.

## Do Not Use

Do not use to run the reproducibility rubric, select a replacement model, tune parameters, edit code, rerun experiments, review the paper, conduct red-team questioning, or approve submission. This Skill must not modify any reviewed input.

## Workflow

Before starting, read `resources.json` and the declared rubric, engine, severity, and finding-contract resources. In a packaged Skill, resolve them under `references/<source path>`.

1. Require normalized model inputs with real `clm_*` evidence and all six score dimensions. Missing or unverifiable inputs produce a blocked report.
2. Snapshot or hash every reviewed input before review.
3. Load only `model-quality.yaml`; do not load reproducibility, paper, red-team, or submission rules.
4. Submit dimension scores, rationales, and current evidence to the deterministic scorecard, then run the model gate once.
5. Report every finding with evidence location, S0-S3 severity, summary, and revision recommendation.
6. Recheck input hashes after review. They must match the pre-review snapshot.
7. Preserve the report and its `input_digest`. Any subsequent input change requires a new review.

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
