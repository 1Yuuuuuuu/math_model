---
name: sensitivity-analyst
description: Use when a reproducible baseline experiment exists and parameter perturbations, robustness, stability, or failure boundaries must be evaluated.
---

# Sensitivity Analyst

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Measure how conclusions change under justified perturbations. Stability is an evidence-backed result, not a default label.

## When to Use

Use after a successful solver run with a reproducible baseline, named parameters, an evaluation function, and a meaningful output metric.

## Do Not Use

Do not use before a valid baseline exists, to replace out-of-sample validation, or to declare a model robust from one successful run.

## Workflow

1. Verify the baseline experiment, output metric, parameter definitions, feasible domains, and seed policy.
2. Choose perturbations from measurement error, plausible scenarios, estimation uncertainty, or policy ranges; record the justification.
3. Change one parameter at a time unless interaction analysis is explicitly designed.
4. Validate the perturbation contract with `cumcm_sensitivity`（仅契约校验：base_params + perturb 形状；**不做求值**）。逐点求值经 Python 库 `cumcm_toolkit.evaluation.sensitivity.sensitivity_report`（注入 evaluate 回调）或由 `cumcm_model_run` + `cumcm_metrics` 重跑同一条求值路径完成；失败点与非线性点如实保留为失败。
5. Compare absolute and relative changes, rankings, feasibility, threshold crossings, and dominant parameters.
6. State the valid domain, unstable regions, failure boundaries, and limits of the design. Record the run with `cumcm_experiment_record` and index outputs with `cumcm_artifact_index`.

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
- Expecting `cumcm_sensitivity` to evaluate points（它只校验输入契约，求值必须走 Python 库或重跑求值路径）。
