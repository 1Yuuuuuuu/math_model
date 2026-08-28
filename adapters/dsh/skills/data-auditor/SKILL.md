---
name: data-auditor
description: Use when competition datasets, tables, CSV files, or derived data need quality checks and a reproducible transformation plan before modeling.
---

# Data Auditor

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Establish what the data can support before modeling. Original inputs are immutable evidence; every transformation must be explicit and reproducible, with the source file never overwritten.

## When to Use

Use after the data inventory exists and before model selection or execution. Typical triggers include missing values, duplicates, mixed units, anomalous ranges, leakage risk, encoding problems, and requested cleaning.

## Do Not Use

Do not use to choose the winning model, tune a result until it looks good, or overwrite original data. Use `problem-reader` first if columns cannot be tied to a question.

## Workflow

1. Identify source files, hashes, encodings, sheets, keys, units, time fields, and target variables.
2. Run `cumcm_data_profile`（cumcm-tools 插件）on each source before any transformation. Record row/column counts, nulls, duplicates, types, ranges, and warnings from the returned profile report.
3. Check target leakage, train/test overlap, temporal ordering, unit consistency, impossible values, and sampling bias.
4. Draft an ordered transformation plan: affected columns, parameters, justification, and reversibility for each step.
5. Apply the plan with `cumcm_data_transform`（JSON `steps`，写出到新路径），retaining the original file and the transformation record.
6. Re-run `cumcm_data_profile` on the transformed output and compare invariants. Store both profiles as evidence; index the outputs with `cumcm_artifact_index`.

## Failure Closure

Unreadable files, unknown encodings, missing keys, ambiguous units, or failed transforms produce `status: blocked`. List the exact item in `missing_inputs` or `failed_step` and state `resume_when`. Do not fabricate repaired values or silently drop rows.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: data-audit
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

Complete evidence includes source identity, pre/post profiles, transformation record, retained/dropped row counts, warnings, and unresolved risks.

## Quick Reference

| Check | Required evidence |
| --- | --- |
| Missing/duplicate/type | profile report (cumcm_data_profile) |
| Cleaning | ordered transform record (cumcm_data_transform) |
| Leakage/split | keys and overlap result |
| Output validity | post-transform profile |

## Common Mistakes

- Editing the source file in place.
- Imputing before identifying why values are missing.
- Normalizing the full dataset before splitting.
- Treating a clean profile as proof that the sample is representative.
