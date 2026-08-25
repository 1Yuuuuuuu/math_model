---
name: sensitivity-analyst
description: Use when a reproducible baseline experiment exists and parameter perturbations, robustness, stability, or failure boundaries must be evaluated.
---

# Sensitivity Analyst

## Overview

Measure how conclusions change under justified perturbations. Stability is an evidence-backed result, not a default label.

## When to Use

Use after a successful solver run with a reproducible baseline, named parameters, an evaluation function, and a meaningful output metric.

## Do Not Use

Do not use before a valid baseline exists, to replace out-of-sample validation, or to declare a model robust from one successful run.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

Before returning `complete`, write every declared output into the competition workspace, index it with the declared artifact index, and call `complete_handoff` with the real workspace, artifact, experiment, and evidence-link records. A format-valid ID without a matching record is not evidence.

1. Verify the baseline experiment, output metric, parameter definitions, feasible domains, and seed policy.
2. Choose perturbations from measurement error, plausible scenarios, estimation uncertainty, or policy ranges; record the justification.
3. Change one parameter at a time unless interaction analysis is explicitly designed.
4. Execute every point through the same evaluation path. Preserve failed and non-finite points as failures.
5. Compare absolute and relative changes, rankings, feasibility, threshold crossings, and dominant parameters.
6. State the valid domain, unstable regions, failure boundaries, and limits of the design.

## Failure Closure

If the baseline is missing, the parameter is unknown, or there are zero valid sensitivity points, return `status: blocked`. Fill `missing_inputs`, `failed_step`, and `resume_when`. Do not fabricate successful points or label the result stable.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: sensitivity-report
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

A complete report includes the baseline, parameter/range justification, requested and valid points, point results, failures, changes, dominant factors, stability scope, and failure boundaries.

## Quick Reference

| Situation | Conclusion |
| --- | --- |
| All points failed | blocked, never stable |
| Unknown parameter | blocked |
| Metric barely changes in tested range | stable only in that range |
| Feasibility/ranking changes | report threshold and instability |

## Common Mistakes

- Calling zero range globally stable without defining the tested domain.
- Dropping failed perturbations from the report.
- Mixing parameter effects with a changed dataset or seed.
- Perturbing arbitrary percentages with no domain justification.
