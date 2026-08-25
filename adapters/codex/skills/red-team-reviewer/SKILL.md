---
name: red-team-reviewer
description: Use when every key CUMCM paper claim needs an independent judge-style challenge, boundary check, and finding report.
---

# Red Team Reviewer

## Overview

Run read-only Gate 4. Challenge every key claim using its support boundary, limitations, counterexamples, stress scenarios, and alternative explanations.

## When to Use

Use after key `clm_*` claims, claim boundaries, limitations, and challenge records are available from an otherwise reviewable paper package.

## Do Not Use

Do not author missing limitations, repair claims, edit the paper, score paper style, or audit submission files. This Skill must not modify reviewed material.

## Workflow

Read `resources.json`; packaged resources resolve under `references/<source path>`.

1. Normalize key claims, boundaries, limitations, and proposed challenges.
2. Verify every key claim has a challenge record and current evidence.
3. Load only `red-team.yaml`; do not use a scorecard.
4. Record additional evidence-bound findings only with `status: open`.
5. Run the engine and write exactly one indexed red-team report.
6. Recheck reviewed file hashes and mark revisions stale.

## Failure Closure

Missing claim coverage, evidence, boundary, or capability yields `status: blocked` when review cannot execute, or a failed report when a checked rule fails. Do not fabricate a challenge outcome, evidence ID, finding, response, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: red-team-review
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff has one indexed report and artifact evidence. A blocked handoff has empty outputs and evidence.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Challenge cannot be verified |
| failed | An open S0/S1 remains |
| passed | Every key claim is covered for this digest |

## Common Mistakes

- Asking generic questions without claim IDs.
- Treating acknowledgement of a limitation as resolution.
- Editing the author's response during independent review.
