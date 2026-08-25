---
name: solver
description: Use when a selected CUMCM model has complete audited inputs and must be executed with reproducible parameters, metrics, and artifacts.
---

# Solver

## Overview

Execute only a verified capability and preserve enough evidence to reproduce the result. Capability checks happen before computation.

## When to Use

Use after a `model-selection` handoff identifies the model, inputs, baseline, metrics, validation design, and acceptance criteria.

## Do Not Use

Do not use for initial model choice, unsupported model execution, purely theoretical explanation, or paper prose. Unsupported cards remain plan-only.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

1. Verify input artifacts, hashes, schema, random seed, model ID, parameters, metric definitions, and output paths.
2. Call `solver_execution_mode(model_id)` from the declared routing helper. Execute only `execute`; treat `plan-only` as unsupported. The verified allowlist is entropy-weight plus TOPSIS evaluation, `linear-regression` prediction, or linear programming with SciPy `linprog`.
3. For an unsupported model, produce an executable plan, missing tool/API, tests, and `resume_when`; do not run a substitute.
4. Run the environment doctor, execute a simple baseline and the selected capability, then create an experiment record whose `environment.lock_sha256` is computed from the workspace `uv.lock`; do not claim a locked environment without that record.
5. Record code identity, parameters, seed, library versions, metrics, warnings, and artifact hashes.
6. Write outputs to the competition workspace, index them, create evidence links, and call `complete_handoff` with the real workspace and records. Reopen and recompute the outputs before marking complete; a format-valid ID without a matching record is not evidence.

## Failure Closure

Missing data, failed capability checks, non-finite outputs, solver failure, or unverifiable artifacts produce `status: blocked`. Populate `missing_inputs`, `failed_step`, and `resume_when`. Do not fabricate a number, convergence claim, optimum, score, or saved artifact.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: solver-run
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

Complete evidence includes experiment identity, input/code hashes, environment, parameters, seed, baseline, metrics, solver status, warnings, and output artifact hashes.

## Quick Reference

| Capability | Phase 3 action |
| --- | --- |
| Entropy weight + TOPSIS | execute verified evaluation chain |
| linear-regression | execute registry runner |
| linear programming | execute `linprog`, require success |
| Any other card | plan-only and blocked execution |

## Common Mistakes

- Replacing an unsupported method with a convenient one without approval.
- Reporting the last iterate as an optimum after solver failure.
- Omitting seed, split, preprocessing, or baseline.
- Copying numbers from console output without an artifact record.
