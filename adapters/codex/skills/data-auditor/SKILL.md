---
name: data-auditor
description: Use when competition datasets, tables, CSV files, or derived data need quality checks and a reproducible transformation plan before modeling.
---

# Data Auditor

## Overview

Establish what the data can support before modeling. Original inputs are immutable evidence; every transformation must be explicit and reproducible.

## When to Use

Use after the data inventory exists and before model selection or execution. Typical triggers include missing values, duplicates, mixed units, anomalous ranges, leakage risk, encoding problems, and requested cleaning.

## Do Not Use

Do not use to choose the winning model, tune a result until it looks good, or overwrite original data. Use `problem-reader` first if columns cannot be tied to a question.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

Before returning `complete`, write every declared output into the competition workspace, index it with the declared artifact index, and call `complete_handoff` with the real workspace, artifact, experiment, and evidence-link records. A format-valid ID without a matching record is not evidence.

1. Identify source files, hashes, encodings, sheets, keys, units, time fields, and target variables.
2. Run the Phase 2 profile API before transformation. Record row/column counts, nulls, duplicates, types, ranges, and warnings.
3. Check target leakage, train/test overlap, temporal ordering, unit consistency, impossible values, and sampling bias.
4. Draft ordered transforms with affected columns, parameters, justification, and reversibility.
5. Write transformed data to a new path; retain the original and transformation record.
6. Re-profile the output and compare invariants. Store both reports as evidence.

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
| Missing/duplicate/type | profile report |
| Cleaning | ordered transform record |
| Leakage/split | keys and overlap result |
| Output validity | post-transform profile |

## Common Mistakes

- Editing the source file in place.
- Imputing before identifying why values are missing.
- Normalizing the full dataset before splitting.
- Treating a clean profile as proof that the sample is representative.
