---
name: submission-auditor
description: Use when a final CUMCM source and PDF candidate need a read-only hard-gate audit against build, citation, PDF, hash, and annual-rule evidence.
---

# Submission Auditor

## Overview

Run read-only Gate 0 for the exact final source/PDF pair. This is a hard submission audit, not a paper-quality or model review.

## When to Use

Use when build, lint, citation, PDF inspection, source/PDF SHA-256, current annual-rule verification, and submission evidence are available.

## Do Not Use

Do not edit LaTeX, rebuild the paper, change citations, repair the PDF, score writing, or approve model quality. This Skill must not modify reviewed material.

## Workflow

Read `resources.json`; packaged resources resolve under `references/<source path>`.

1. Normalize the four Phase 4 reports, both hashes, annual-rule decision, and evidence.
2. Snapshot the exact final files and load only `submission.yaml`.
3. Check build, lint, citations, PDF readability, blank pages, hashes, and annual rule.
4. Run the engine without a scorecard.
5. Write exactly one indexed submission-audit report.
6. Recheck hashes; any final-file change invalidates the report.

## Failure Closure

Missing final files, current rules, capabilities, hashes, or evidence yields `status: blocked` with empty outputs/evidence and resume conditions. Do not fabricate a rule check, hash, PDF result, finding, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: submission-audit
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff contains one indexed audit report and artifact evidence. A blocked handoff contains neither.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Hard-gate inputs cannot be verified |
| failed | A submission S0/S1 exists |
| passed | This exact source/PDF pair passes Gate 0 |

## Common Mistakes

- Auditing a PDF different from the recorded hash.
- Treating last year's rules as current.
- Fixing files inside the independent audit.
