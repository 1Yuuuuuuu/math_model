---
name: model-selector
description: Use when a defined modeling question and audited data must be matched to candidate mathematical models, baselines, and a verification plan.
---

# Model Selector

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Select a defensible model family from the shared catalog (`shared/knowledge/model-catalog.yaml` + `shared/knowledge/model-cards/`) by matching assumptions and validation needs, not by prestige or familiarity.

## When to Use

Use after question decomposition and data audit, when several evaluation, prediction, optimization, classification, statistics, or data-processing methods could answer the task.

## Do Not Use

Do not use to execute a chosen model, manufacture performance metrics, or hide missing data. Use `solver` only after the selection handoff is complete.

DSH 侧没有"模型选择"专用工具：候选对比、假设匹配与验证方案设计由模型按本 Skill 的流程完成；只有人工门通过后，`solver` 才用 `cumcm_model_run` 执行。

## Workflow

1. Read `shared/knowledge/model-catalog.yaml`; open only the cards relevant to the objective and data type.
2. Reject candidates whose prohibited scenarios or assumptions conflict with observed evidence.
3. Compare at least one simple baseline and viable alternatives using inputs, assumptions, interpretability, cost, validation, sensitivity needs, and failure signs.
4. Name the preferred candidate conditionally and record why alternatives lost.
5. Define preprocessing boundaries, metrics, split/design, diagnostics, parameter ranges, and acceptance criteria before execution.
6. Mark capability status honestly: DSH 侧 `cumcm_model_run` 的 registry 仅含 linear-regression / decision-tree / kmeans，这些可标为 `verified-executable`；其余模型卡（熵权-TOPSIS、线性规划等）在 DSH 轨道无 runner，只能标 `plan-only` 并注明缺失的执行面。

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
| Ready to execute | registry model (linear-regression / decision-tree / kmeans) + complete input contract; otherwise plan-only |

## Common Mistakes

- Picking a complex model without a baseline.
- Treating correlation as causal justification.
- Selecting on in-sample fit alone.
- Writing "the model performs well" before execution, or marking a non-registry model as executable on the DSH track.
