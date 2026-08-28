---
name: solver
description: Use when a selected CUMCM model has complete audited inputs and must be executed with reproducible parameters, metrics, and artifacts.
---

# Solver

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Execute only a verified capability and preserve enough evidence to reproduce the result. Capability checks happen before computation; unsupported models stay plan-only.

## When to Use

Use after a `model-selection` handoff identifies the model, inputs, baseline, metrics, validation design, and acceptance criteria.

## Do Not Use

Do not use for initial model choice, unsupported model execution, purely theoretical explanation, or paper prose. Unsupported cards remain plan-only.

DSH 侧执行面受限：`cumcm_model_run` 只运行 registry 内的 linear-regression / decision-tree / kmeans；Codex 轨道的熵权-TOPSIS 与 SciPy `linprog` 链在 DSH 无 runner，**不得**用 registry 模型或手工计算冒充替代品。

## Workflow

1. Verify input artifacts, hashes, schema, random seed, model ID, parameters, metric definitions, and output paths.
2. Check execution eligibility against the registry（cumcm_model_run 支持的 name：linear-regression / decision-tree / kmeans）。Eligible models proceed; everything else is `plan-only`.
3. For an unsupported model, produce an executable plan, the missing tool/API, tests, and `resume_when`; do not run a substitute.
4. Run the environment doctor via the Python library `cumcm_toolkit.environment.doctor.doctor()`（检查 python 3.11 / uv / xelatex / latexmk），then execute a simple baseline and the selected capability with `cumcm_model_run`（name / X / y / seed / params）。
5. Compute metrics with `cumcm_metrics`（kind: regression | classification）；create the experiment record with `cumcm_experiment_record`，its `environment.lock_sha256` is computed from the workspace `uv.lock` via `project_root`；do not claim a locked environment without that record.
6. Export result tables with `cumcm_result_export`（json/csv/latex），link claims with `cumcm_evidence_link`，index outputs with `cumcm_artifact_index`，and close the handoff with the real workspace and records. Reopen and recompute the outputs before marking complete; a format-valid ID without a matching record is not evidence.

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

| Capability | DSH action |
| --- | --- |
| linear-regression | execute registry runner via cumcm_model_run |
| decision-tree / kmeans | execute registry runner via cumcm_model_run |
| Entropy weight + TOPSIS | plan-only on DSH track（无 runner） |
| linear programming (linprog) | plan-only on DSH track（无 runner） |
| Any other card | plan-only and blocked execution |

## Common Mistakes

- Replacing an unsupported method with a convenient one without approval.
- Reporting the last iterate as an optimum after solver failure.
- Omitting seed, split, preprocessing, or baseline.
- Copying numbers from console output without an artifact record.
