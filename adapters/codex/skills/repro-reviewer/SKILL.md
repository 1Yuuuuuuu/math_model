---
name: repro-reviewer
description: Use when five completed CUMCM modeling handoffs need an independent reproducibility and provenance audit.
---

# Repro Reviewer

## Overview

Run read-only Gate 1. Verify that Phase 3 handoffs resolve to real artifacts, successful experiments, evidence links, and an environment-lock identity.

## When to Use

Use after all five modeling handoffs and their artifact, experiment, and evidence indexes exist. Rerun after any indexed record or reviewed file changes.

## Do Not Use

Do not score model quality, repair an experiment, rerun code, edit handoffs, review prose, or approve submission. This Skill must not modify reviewed material.

## Workflow

Read `resources.json`; packaged resources resolve under `references/<source path>`.

1. Normalize the five handoffs with `build_reproducibility_inputs`.
2. Reject missing records, failed experiments, missing lock hashes, broken evidence links, and unindexed outputs.
3. Snapshot every reviewed file and load only `reproducibility.yaml`.
4. Run the review engine without a scorecard or another gate's rubric.
5. Write exactly one contract-valid, indexed reproducibility report.
6. Recheck file hashes; any change makes the report stale.

## Failure Closure

Missing or unverifiable material yields `status: blocked`, empty outputs/evidence, a failed step, and concrete resume conditions. Do not fabricate an ID, experiment result, hash, finding, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: repro-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff has one indexed report output and artifact evidence. A blocked handoff has neither.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Inputs cannot be verified |
| failed | An open S0/S1 exists |
| passed | This exact reproducibility digest passes |

## Common Mistakes

- Treating well-formed IDs as proof that records exist.
- Approving a successful run without its lock hash.
- Mixing model-quality scoring into Gate 1.
