---
name: problem-reader
description: Use when a CUMCM problem statement, attachment note, or competition prompt must be decomposed into explicit modeling requirements before data processing or model selection.
---

# Problem Reader

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Analyze only the supplied statement and attachments—never memory of a similar contest problem—and turn them into explicit modeling requirements. Ambiguity is preserved and recorded, not resolved by inventing facts.

## When to Use

Use for initial problem reading, sub-question decomposition, objective/constraint extraction, symbol planning, attachment inventory, and assumption logging.

## Do Not Use

Do not use to select the final model, run computations, write the final paper, or approve citations. Hand the result to `data-auditor` and `model-selector` when ready.

DSH 侧没有"问题解析"专用工具：拆解、目标/约束抽取与符号规划由模型按本 Skill 的流程完成，不调用任何 cumcm_* 工具代劳。

## Workflow

1. Inventory the exact problem text, attachments, tables, units, time range, and requested deliverables.
2. Split every explicit question into an answerable objective; record dependencies between questions.
3. For each objective, list inputs, outputs, constraints, evaluation criteria, and unresolved terms.
4. Separate stated facts from proposed assumptions; every assumption needs a reason and a validation route.
5. Produce a data-needs table and stop on missing material that changes the mathematical problem.
6. Save the problem analysis as a workspace artifact, index it with `cumcm_artifact_index`（cumcm-tools 插件）, then close the handoff with the real artifact record. A format-valid ID without a matching record is not evidence.

## Failure Closure

If the statement or a referenced attachment is missing, return `status: blocked`, identify it in `missing_inputs`, set `failed_step`, and state `resume_when`. Do not fabricate omitted constraints, data, units, or task wording.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: problem-analysis
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

A complete output contains: question list, objective/constraint table, data inventory, symbol draft, assumptions with validation routes, and open questions.

## Quick Reference

| Observation | Record as |
| --- | --- |
| Explicit sentence in prompt | stated fact + location |
| Necessary but unstated condition | proposed assumption |
| Missing attachment or column | blocker |
| Possible method | downstream candidate, not decision |

## Common Mistakes

- Treating an example value as a universal constraint.
- Combining two questions with different objectives.
- Selecting a familiar model before identifying the output and validation target.
- Hiding missing data inside an assumption.
