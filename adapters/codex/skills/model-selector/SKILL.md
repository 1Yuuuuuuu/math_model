---
name: model-selector
description: Use when a defined modeling question and audited data must be matched to candidate mathematical models, baselines, and a verification plan.
---

# Model Selector

## Overview

Select a defensible model family from the shared catalog by matching assumptions and validation needs, not by prestige or familiarity.

## When to Use

Use after question decomposition and data audit, when several evaluation, prediction, optimization, classification, statistics, or data-processing methods could answer the task.

## Do Not Use

Do not use to execute a chosen model, manufacture performance metrics, or hide missing data. Use `solver` only after the selection handoff is complete.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

Before returning `complete`, write every declared output into the competition workspace, index it with the declared artifact index, and call `complete_handoff` with the real workspace, artifact, experiment, and evidence-link records. A format-valid ID without a matching record is not evidence.

1. Read `model-catalog.yaml`; open only cards relevant to the objective and data type.
2. Reject candidates whose prohibited scenarios or assumptions conflict with observed evidence.
3. Compare at least one simple baseline and viable alternatives using inputs, assumptions, interpretability, cost, validation, sensitivity needs, and failure signs.
4. Name the preferred candidate conditionally and record why alternatives lost.
5. Define preprocessing boundaries, metrics, split/design, diagnostics, parameter ranges, and acceptance criteria before execution.
6. Mark capability as `verified-executable` only for Phase 2 representative chains; otherwise mark it `plan-only` with the missing tool.

## Failure Closure

If objectives, audited inputs, outcome definition, or a valid comparison are absent, return `status: blocked`. Populate `missing_inputs`, `failed_step`, and `resume_when`. Do not fabricate model scores or claim a recommended model has run.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: model-selection
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

A complete comparison records candidate card IDs, eligibility, baseline, assumptions, metrics, validation design, capability status, and rejection reasons.

## Quick Reference

| Decision | Evidence |
| --- | --- |
| Candidate eligible | card assumptions match data |
| Candidate rejected | prohibited scenario or failed prerequisite |
| Preferred candidate | comparison against baseline/alternatives |
| Ready to execute | verified tool + complete input contract |

## Common Mistakes

- Picking a complex model without a baseline.
- Treating correlation as causal justification.
- Selecting on in-sample fit alone.
- Writing "the model performs well" before execution.
