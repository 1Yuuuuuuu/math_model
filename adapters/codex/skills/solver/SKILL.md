---
name: solver
description: Use when a selected CUMCM model has complete audited inputs and must be executed with reproducible parameters, metrics, and artifacts.
---

# Solver

## Overview

Execute only a capability returned by the live registry and preserve enough evidence to reproduce the result. Capability checks happen before computation.

## When to Use

Use after a `model-selection` handoff identifies the model, inputs, baseline, metrics, validation design, and acceptance criteria.

## Do Not Use

Do not use for initial model choice, unsupported model execution, purely theoretical explanation, or paper prose. Unsupported cards remain plan-only.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

1. Verify input artifacts, hashes, schema, random seed, model ID, parameters, metric definitions, and output paths.
2. Call `list_capabilities()` from `cumcm_toolkit.models.specifications`, then call `solver_execution_mode(model_id)` from the declared routing helper. A registered capability routes to `execute`; `plan-only` is unsupported. Never replace this live check with a remembered or hard-coded allowlist.
3. For an unsupported model, produce an executable plan, missing tool/API, tests, and `resume_when`; do not run a substitute.
4. Run the environment doctor, execute a simple baseline, then call `cumcm_toolkit.models.execution.execute(model_id, payload)`. This is the JSON-only Codex/DSH contract. The legacy `run_model(name, X, y)` entry point exists only for older Python callers and returns a fitted estimator; do not use it for a Skill or DSH handoff.
5. Create an experiment record whose `environment.lock_sha256` is computed from the workspace `uv.lock`; do not claim a locked environment without that record.
6. Record code identity, parameters, seed, library versions, metrics, warnings, and artifact hashes.
7. Write outputs to the competition workspace, index them, create evidence links, and call `complete_handoff` with the real workspace and records. Reopen and recompute the outputs before marking complete; a format-valid ID without a matching record is not evidence.

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

| Registry result | Action |
| --- | --- |
| `list_capabilities()` contains `model_id` and route is `execute` | call public `execute(model_id, payload)` |
| knowledge card exists but registry omits `model_id` | plan-only and blocked execution |
| unknown `model_id` | plan-only and blocked execution |
| `execute` raises `ValueError` | preserve the error stage; return blocked without partial results |

Names such as `linear-regression` and linear programming are executable only when the current registry returns them; the examples are not an allowlist.

## Common Mistakes

- Replacing an unsupported method with a convenient one without approval.
- Reporting the last iterate as an optimum after solver failure.
- Omitting seed, split, preprocessing, or baseline.
- Copying numbers from console output without an artifact record.
- Calling legacy `run_model` and placing its estimator in a Codex/DSH handoff.
- Inventing a capability from a knowledge card instead of querying `list_capabilities()`.
